import re
import io
import wave
import shlex
import subprocess
import collections
import logging
from collections import defaultdict
from pathlib import Path
from typing import (
    Optional,
    Iterable,
    Callable,
    Dict,
    List,
    TextIO,
    Any,
    BinaryIO,
    Mapping,
    Set,
)

import pydash

logger = logging.getLogger("voice2json")

# -----------------------------------------------------------------------------


def convert_wav(profile: Dict[str, Any], wav_data: bytes) -> bytes:
    """Converts WAV data to 16-bit, 16Khz mono."""
    convert_cmd_str = pydash.get(
        profile,
        "audio.convert-command",
        "sox -t wav - -r 16000 -e signed-integer -b 16 -c 1 -t wav -",
    )
    convert_cmd = shlex.split(convert_cmd_str)
    logger.debug(convert_cmd)
    return subprocess.run(
        convert_cmd, check=True, stdout=subprocess.PIPE, input=wav_data
    ).stdout


def maybe_convert_wav(profile: Dict[str, Any], wav_data: bytes) -> bytes:
    """Converts WAV data to 16-bit, 16Khz mono WAV if necessary."""
    with io.BytesIO(wav_data) as wav_io:
        with wave.open(wav_io, "rb") as wav_file:
            rate, width, channels = (
                wav_file.getframerate(),
                wav_file.getsampwidth(),
                wav_file.getnchannels(),
            )
            if (rate != 16000) or (width != 2) or (channels != 1):
                # Do conversion
                if rate < 16000:
                    # Probably being given 8Khz audio
                    logger.warning(f"Upsampling audio from {rate} Hz. Expect poor performance!")

                return convert_wav(profile, wav_data)
            else:
                # Return original data
                return wav_data


def buffer_to_wav(buffer: bytes) -> bytes:
    """Wraps a buffer of raw audio data (16-bit, 16Khz mono) in a WAV"""
    with io.BytesIO() as wav_buffer:
        with wave.open(wav_buffer, mode="wb") as wav_file:
            wav_file.setframerate(16000)
            wav_file.setsampwidth(2)
            wav_file.setnchannels(1)
            wav_file.writeframesraw(buffer)

        return wav_buffer.getvalue()


def should_convert_wav(wav_io: BinaryIO) -> bool:
    with wave.open(wav_io, "rb") as wav_file:
        rate, width, channels = (
            wav_file.getframerate(),
            wav_file.getsampwidth(),
            wav_file.getnchannels(),
        )

        return (rate != 16000) or (width != 2) or (channels != 1)


# -----------------------------------------------------------------------------


def ppath(
    profile, profile_dir: Path, query: str, default: Optional[str] = None
) -> Optional[Path]:
    """Returns a Path from a profile or a default Path relative to the profile directory."""
    result = pydash.get(profile, query)
    if result is None:
        if default is not None:
            result = profile_dir / Path(default)
    else:
        result = Path(result)

    return result


# -----------------------------------------------------------------------------


def read_dict(
    dict_file: Iterable[str],
    word_dict: Optional[Dict[str, List[str]]] = None,
    transform: Optional[Callable[[str], str]] = None,
    silence_words: Optional[Set[str]] = None,
) -> Dict[str, List[str]]:
    """
    Loads a CMU/Julius word dictionary, optionally into an existing Python dictionary.
    """
    if word_dict is None:
        word_dict = {}

    for i, line in enumerate(dict_file):
        line = line.strip()
        if len(line) == 0:
            continue

        try:
            # Use explicit whitespace (avoid 0xA0)
            parts = re.split(r"[ \t]+", line)
            word = parts[0]

            # Skip Julius extras
            parts = [p for p in parts[1:] if p[0] not in ["[", "@"]]

            idx = word.find("(")
            if idx > 0:
                word = word[:idx]

            if "+" in word:
                # Julius format word1+word2
                words = word.split("+")
            else:
                words = [word]

            for word in words:
                # Don't transform silence words
                if transform and ((silence_words is None) or (word not in silence_words)):
                    word = transform(word)

                pronounce = " ".join(parts)

                if word in word_dict:
                    word_dict[word].append(pronounce)
                else:
                    word_dict[word] = [pronounce]
        except Exception as e:
            logger.warning(f"read_dict: {e} (line {i+1})")

    return word_dict


# -----------------------------------------------------------------------------


def align2json(align_file: TextIO) -> Dict[str, Any]:
    """Converts a word_align.pl word error rate text file to JSON."""
    STATE_EXPECTED = 0
    STATE_ACTUAL = 1
    STATE_ACCURACY = 2
    STATE_STATS = 3

    pattern_utterance = re.compile(r"\s*([^(]+)\s*\(([^)]+)\)\s*$")
    pattern_errors = re.compile(
        r"words:\s*([0-9]+)\s+correct:\s*([0-9]+)\s+errors:\s*([0-9]+)", re.IGNORECASE
    )
    results = defaultdict(dict)

    state = STATE_EXPECTED
    utterance_id = None
    for line in align_file:
        line = line.strip()
        if line.startswith("TOTAL"):
            continue

        if state == STATE_EXPECTED:
            match = pattern_utterance.match(line)
            utterance_id = match.group(2).strip()
            results[utterance_id]["expected"] = match.group(1).strip()
            state = STATE_ACTUAL
        elif state == STATE_ACTUAL:
            match = pattern_utterance.match(line)
            assert utterance_id == match.group(2).strip()
            results[utterance_id]["actual"] = match.group(1).strip()
            state = STATE_ACCURACY
        elif state == STATE_ACCURACY:
            match = pattern_errors.search(line)
            words = int(match.group(1))
            correct = int(match.group(2))
            errors = int(match.group(3))
            results[utterance_id]["words"] = words
            results[utterance_id]["correct"] = correct
            results[utterance_id]["errors"] = errors
            state = STATE_STATS
        elif state == STATE_STATS:
            state = STATE_EXPECTED
            utterance_id = None

    return results


def get_audio_source(profile: Dict[str, Any]) -> BinaryIO:
    """Starts a recording subprocess for raw 16-bit 16Khz mono audio"""
    record_cmd_str = pydash.get(
        profile, "audio.record-command", "arecord -q -r 16000 -c 1 -f S16_LE -t raw"
    )
    record_cmd = shlex.split(record_cmd_str)
    logger.debug(record_cmd)
    record_proc = subprocess.Popen(record_cmd, stdout=subprocess.PIPE)
    return record_proc.stdout


# -----------------------------------------------------------------------------


def recursive_update(base_dict: Dict[Any, Any], new_dict: Mapping[Any, Any]) -> None:
    """Recursively overwrites values in base dictionary with values from new dictionary"""
    for k, v in new_dict.items():
        if isinstance(v, collections.Mapping) and (k in base_dict):
            recursive_update(base_dict[k], v)
        else:
            base_dict[k] = v
