"""Support for Julius speech to text engine."""
import io
import logging
import os
import shutil
import subprocess
import tempfile
import time
import typing
import wave
from pathlib import Path

import networkx as nx
import rhasspynlu
from rhasspyasr import Transcriber, Transcription
from rhasspynlu.g2p import PronunciationsType

from .core import Voice2JsonCore
from .utils import get_wav_duration

_LOGGER = logging.getLogger("voice2json.julius")

# -----------------------------------------------------------------------------


class JuliusTranscriber(Transcriber):
    """Transcriber for Julius speech to text engine."""

    def __init__(
        self,
        core: Voice2JsonCore,
        model_dir: typing.Union[str, Path],
        dictionary: typing.Union[str, Path],
        language_model: typing.Union[str, Path],
        max_empty_lines: int = 10,
        debug: bool = False,
    ):
        self.core = core
        self.model_dir = Path(model_dir)
        self.dictionary = Path(dictionary)
        self.language_model = Path(language_model)
        self.julius_proc: typing.Optional[subprocess.Popen] = None
        self.temp_dir: typing.Optional[tempfile.TemporaryDirectory] = None
        self.julius_in: typing.Optional[typing.TextIO] = None
        self.julius_out: typing.Optional[typing.TextIO] = None
        self.max_empty_lines = max_empty_lines
        self.debug = debug

    def start_julius(self):
        """Start Julius process."""
        _LOGGER.debug("Starting Julius")
        self.temp_dir = tempfile.TemporaryDirectory()

        fifo_path = os.path.join(self.temp_dir.name, "filelist")
        os.mkfifo(fifo_path)

        julius_cmd = [
            "julius",
            "-nosectioncheck",
            "-C",
            str(self.model_dir / "julius.jconf"),
            "-input",
            "file",
            "-filelist",
            fifo_path,
            "-nocutsilence",
            "-norealtime",
            "-v",
            str(self.dictionary),
        ]

        if not self.debug:
            julius_cmd.append("-quiet")

        dnn_conf = self.model_dir / "dnn.jconf"
        if dnn_conf.exists():
            # DNN model
            julius_cmd.extend(["-dnnconf", str(dnn_conf)])

        if self.language_model.suffix.lower() == ".txt":
            # ARPA forward n-grams
            julius_cmd.extend(["-nlr", str(self.language_model)])
        else:
            # Binary n-gram
            julius_cmd.extend(["-d", str(self.language_model)])

        _LOGGER.debug(julius_cmd)

        # Start Julius server
        stderr = subprocess.DEVNULL
        if self.debug:
            stderr = None

        self.julius_proc = subprocess.Popen(
            julius_cmd, stdout=subprocess.PIPE, stderr=stderr, universal_newlines=True
        )

        self.julius_out = open(fifo_path, "w")

        # -----

        # Read until Julius has started
        line = self.julius_proc.stdout.readline().lower().strip()
        if self.debug:
            _LOGGER.debug("Julius: %s", line)

        if "error" in line:
            raise Exception(line)

        while "system information end" not in line:
            line = self.julius_proc.stdout.readline().lower().strip()
            if self.debug:
                _LOGGER.debug("Julius: %s", line)

            if "error" in line:
                raise Exception(line)

        self.julius_in = self.julius_proc.stdout

        _LOGGER.debug("Julius started")

    def stop(self):
        """Stop transcriber."""
        if self.julius_out is not None:
            self.julius_out.close()
            self.julius_out = None

        if self.temp_dir is not None:
            self.temp_dir.cleanup()
            self.temp_dir = None

        if self.julius_proc is not None:
            _LOGGER.debug("Stopping Julius")
            self.julius_proc.terminate()
            self.julius_proc.wait()
            self.julius_proc = None
            _LOGGER.debug("Stopped Julius")

    def transcribe_wav(self, wav_bytes: bytes) -> typing.Optional[Transcription]:
        """Transcribe WAV data."""
        if not self.julius_proc:
            self.start_julius()

        assert self.julius_in and self.julius_out, "Julius not started"

        # Compute WAV duration
        wav_duration = get_wav_duration(wav_bytes)

        # Write path to WAV file
        _LOGGER.debug("Sending %s byte(s) to Julius", len(wav_bytes))
        start_time = time.time()

        with tempfile.NamedTemporaryFile(suffix=".wav", mode="wb+") as temp_file:
            temp_file.write(wav_bytes)
            temp_file.seek(0)

            print(temp_file.name, file=self.julius_out)
            self.julius_out.flush()

            sentence_line = ""
            line = self.julius_in.readline().strip()
            _LOGGER.debug("Julius> %s", line)

            num_empty_lines = 0
            while True:
                if line.startswith("sentence1:"):
                    sentence_line = line.split(":", maxsplit=1)[1]
                    break

                if "error" in line.lower():
                    # Give up with an empty transcription
                    _LOGGER.warning(line)
                    break

                line = self.julius_in.readline().strip()
                _LOGGER.debug("Julius> %s", line)

                if not line:
                    num_empty_lines += 1

                if num_empty_lines >= self.max_empty_lines:
                    break

            # Exclude <s> and </s>
            _LOGGER.debug(sentence_line)
            result_text = sentence_line.replace("<s>", "").replace("</s>", "").strip()
            end_time = time.time()

        result_text = result_text.strip()

        return Transcription(
            text=result_text,
            transcribe_seconds=end_time - start_time,
            wav_seconds=wav_duration,
            likelihood=1,
        )

    def transcribe_stream(
        self,
        audio_stream: typing.Iterable[bytes],
        sample_rate: int,
        sample_width: int,
        channels: int,
    ) -> typing.Optional[Transcription]:
        """Speech to text from an audio stream."""
        # No online streaming support.
        # Re-package as a WAV.
        with io.BytesIO() as wav_buffer:
            wav_file: wave.Wave_write = wave.open(wav_buffer, "wb")
            with wav_file:
                wav_file.setframerate(sample_rate)
                wav_file.setsampwidth(sample_width)
                wav_file.setnchannels(channels)

                for frame in audio_stream:
                    wav_file.writeframes(frame)

            return self.transcribe_wav(wav_buffer.getvalue())


# -----------------------------------------------------------------------------


def train(
    graph: nx.DiGraph,
    dictionary: typing.Union[str, Path],
    language_model: typing.Union[str, Path],
    pronunciations: PronunciationsType,
    dictionary_word_transform: typing.Optional[typing.Callable[[str], str]] = None,
    silence_words: typing.Optional[typing.Set[str]] = None,
    g2p_model: typing.Optional[typing.Union[str, Path]] = None,
    g2p_word_transform: typing.Optional[typing.Callable[[str], str]] = None,
    missing_words_path: typing.Optional[typing.Union[str, Path]] = None,
    vocab_path: typing.Optional[typing.Union[str, Path]] = None,
    language_model_fst: typing.Optional[typing.Union[str, Path]] = None,
    base_language_model_fst: typing.Optional[typing.Union[str, Path]] = None,
    base_language_model_weight: typing.Optional[float] = None,
    mixed_language_model_fst: typing.Optional[typing.Union[str, Path]] = None,
    balance_counts: bool = True,
):
    """Re-generates language model and dictionary from intent graph"""
    vocabulary: typing.Set[str] = set()

    if silence_words:
        vocabulary.update(silence_words)

    if vocab_path:
        vocab_file = open(vocab_path, "w+")
    else:
        vocab_file = typing.cast(
            typing.TextIO, tempfile.NamedTemporaryFile(suffix=".txt", mode="w+")
        )
        vocab_path = vocab_file.name

    # Language model mixing
    is_mixing = False
    base_fst_weight = None
    if (
        (base_language_model_fst is not None)
        and (base_language_model_weight is not None)
        and (base_language_model_weight > 0)
    ):
        is_mixing = True
        base_fst_weight = (base_language_model_fst, base_language_model_weight)

    # Begin training
    with tempfile.NamedTemporaryFile(mode="w+") as lm_file:
        with vocab_file:
            # Create language model
            _LOGGER.debug("Converting to ARPA language model")
            rhasspynlu.arpa_lm.graph_to_arpa(
                graph,
                lm_file.name,
                vocab_path=vocab_path,
                model_path=language_model_fst,
                base_fst_weight=base_fst_weight,
                merge_path=mixed_language_model_fst,
            )

            # Load vocabulary
            vocab_file.seek(0)
            vocabulary.update(line.strip() for line in vocab_file)

            if is_mixing:
                # Add all known words
                vocabulary.update(pronunciations.keys())

        assert vocabulary, "No words in vocabulary"

        # Write dictionary to temporary file
        with tempfile.NamedTemporaryFile(mode="w+") as dictionary_file:
            _LOGGER.debug("Writing pronunciation dictionary")
            rhasspynlu.g2p.write_pronunciations(
                vocabulary,
                pronunciations,
                dictionary_file.name,
                g2p_model=g2p_model,
                g2p_word_transform=g2p_word_transform,
                missing_words_path=missing_words_path,
                number_repeated_words=False,
            )

            # -----------------------------------------------------------------

            # Copy dictionary over real file
            dictionary_file.seek(0)
            shutil.copy(dictionary_file.name, dictionary)
            _LOGGER.debug("Wrote dictionary to %s", str(dictionary))

            # Copy language model over real file
            lm_file.seek(0)
            shutil.copy(lm_file.name, language_model)
            _LOGGER.debug("Wrote language model to %s", str(language_model))
