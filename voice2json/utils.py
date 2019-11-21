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
from num2words import num2words

WHITESPACE_PATTERN = re.compile(r"\s+")

logger = logging.getLogger("voice2json")

# -----------------------------------------------------------------------------


def convert_wav(profile: Dict[str, Any], wav_data: bytes) -> bytes:
    """Converts WAV data to expected audio format."""
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
    """Converts WAV data to expected audio format, if necessary."""
    expected_rate = int(pydash.get(profile, "audio.format.sample-rate-hertz", 16000))
    expected_width = int(pydash.get(profile, "audio.format.sample-width-bits", 16)) // 8
    expected_channels = int(pydash.get(profile, "audio.format.channel-count", 1))

    with io.BytesIO(wav_data) as wav_io:
        with wave.open(wav_io, "rb") as wav_file:
            rate, width, channels = (
                wav_file.getframerate(),
                wav_file.getsampwidth(),
                wav_file.getnchannels(),
            )
            if (
                (rate != expected_rate)
                or (width != expected_width)
                or (channels != expected_channels)
            ):
                logger.debug(
                    "Got %s Hz, %s byte(s), %s channel(s). Needed %s Hz, %s byte(s), %s channel(s)",
                    rate,
                    width,
                    channels,
                    expected_rate,
                    expected_width,
                    expected_channels,
                )

                # Do conversion
                if rate < expected_rate:
                    # Probably being given 8Khz audio
                    logger.warning(
                        "Upsampling audio from %s to %s Hz. Expect poor performance!",
                        rate,
                        expected_rate,
                    )

                return convert_wav(profile, wav_data)
            else:
                # Return original data
                return wav_data


def buffer_to_wav(profile: Dict[str, Any], buffer: bytes) -> bytes:
    """Wraps a buffer of raw audio data in a WAV"""
    rate = int(pydash.get(profile, "audio.format.sample-rate-hertz", 16000))
    width = int(pydash.get(profile, "audio.format.sample-width-bits", 16)) // 8
    channels = int(pydash.get(profile, "audio.format.channel-count", 1))

    with io.BytesIO() as wav_buffer:
        with wave.open(wav_buffer, mode="wb") as wav_file:
            wav_file.setframerate(rate)
            wav_file.setsampwidth(width)
            wav_file.setnchannels(channels)
            wav_file.writeframesraw(buffer)

        return wav_buffer.getvalue()


def should_convert_wav(profile: Dict[str, Any], wav_io: BinaryIO) -> bool:
    expected_rate = int(pydash.get(profile, "audio.format.sample-rate-hertz", 16000))
    expected_width = int(pydash.get(profile, "audio.format.sample-width-bits", 16)) // 8
    expected_channels = int(pydash.get(profile, "audio.format.channel-count", 1))

    with wave.open(wav_io, "rb") as wav_file:
        rate, width, channels = (
            wav_file.getframerate(),
            wav_file.getsampwidth(),
            wav_file.getnchannels(),
        )

        return (
            (rate != expected_rate)
            or (width != expected_width)
            or (channels != expected_channels)
        )


def get_wav_duration(wav_bytes: bytes) -> float:
    with io.BytesIO(wav_data) as wav_buffer:
        with wave.open(wav_buffer) as wav_file:
            frames = wav_file.getnframes()
            rate = wav_file.getframerate()
            return frames / float(rate)


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
                if transform and (
                    (silence_words is None) or (word not in silence_words)
                ):
                    word = transform(word)

                pronounce = " ".join(parts)

                if word in word_dict:
                    word_dict[word].append(pronounce)
                else:
                    word_dict[word] = [pronounce]
        except Exception as e:
            logger.warning("read_dict: %s (line %s)", e, i + 1)

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


# -----------------------------------------------------------------------------


def recursive_update(base_dict: Dict[Any, Any], new_dict: Mapping[Any, Any]) -> None:
    """Recursively overwrites values in base dictionary with values from new dictionary"""
    for k, v in new_dict.items():
        if isinstance(v, collections.Mapping) and (k in base_dict):
            recursive_update(base_dict[k], v)
        else:
            base_dict[k] = v


# -----------------------------------------------------------------------------


def numbers_to_words(
    sentence: str, language: Optional[str] = None, add_substitution: bool = False
) -> str:
    """Replaces numbers with words in a sentence. Optionally substitues number back in."""
    words = split_whitespace(sentence)
    changed = False
    for i, word in enumerate(words):
        try:
            number = float(word)

            # 75 -> seventy-five -> seventy five
            words[i] = num2words(number, lang=language).replace("-", " ")

            if add_substitution:
                # Empty substitution for everything but last word.
                # seventy five -> seventy: five:75
                number_words = [w + ":" for w in split_whitespace(words[i])]
                number_words[-1] += word
                words[i] = " ".join(number_words)

            changed = True
        except ValueError:
            pass  # not a number
        except NotImplementedError:
            break  # unsupported language

    if not changed:
        return sentence

    return " ".join(words)


# -----------------------------------------------------------------------------


def split_whitespace(text: str) -> List[str]:
    return WHITESPACE_PATTERN.split(text)
