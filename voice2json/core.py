import logging
import io
import wave
import shlex
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, Union, Set

import pydash
import pywrapfst as fst

from voice2json.train import train_profile
from voice2json.speech.const import KaldiModelType
from voice2json.speech import (
    Transcriber,
    PocketsphinxTranscriber,
    KaldiCommandLineTranscriber,
    KaldiExtensionTranscriber,
    JuliusTranscriber,
)
from voice2json.intent import StrictRecognizer, FuzzyRecognizer
from voice2json.intent.const import Recognizer

_LOGGER = logging.getLogger(__name__)

# -----------------------------------------------------------------------------


class Voice2JsonCore:
    """Core voice2json command support."""

    def __init__(self, profile_dir: Path, profile: Dict[str, Any]):
        """Initialize voice2json."""
        self.profile_dir = profile_dir
        self.profile = profile

    # -------------------------------------------------------------------------
    # train-profile
    # -------------------------------------------------------------------------

    def train_profile(self, db_path: Optional[Path] = None):
        """Generate speech/intent artifacts for a profile."""
        if db_path is not None:
            doit_args = ["--db-file", str(db_path)]
        else:
            # Store in profile directory
            doit_args = ["--db-file", str(self.profile_dir / ".doit.db")]

        train_profile(self.profile_dir, self.profile, doit_args)

    # -------------------------------------------------------------------------
    # transcribe-wav
    # -------------------------------------------------------------------------

    def get_transcriber(self, open_transcription=False, debug=False) -> Transcriber:
        """Create Transcriber based on profile speech system."""
        # Load settings
        acoustic_model_type = pydash.get(
            self.profile, "speech-to-text.acoustic-model-type", "pocketsphinx"
        ).lower()

        if acoustic_model_type == "kaldi":
            # Kaldi
            return self.get_kaldi_transcriber(
                open_transcription=open_transcription, debug=debug
            )
        elif acoustic_model_type == "julius":
            # Julius
            return self.get_julius_transcriber(
                open_transcription=open_transcription, debug=debug
            )
        else:
            # Pocketsphinx (default)
            return self.get_pocketsphinx_transcriber(
                open_transcription=open_transcription, debug=debug
            )

    def get_pocketsphinx_transcriber(
        self, open_transcription=False, debug=False
    ) -> PocketsphinxTranscriber:
        """Create Transcriber for Pocketsphinx."""
        # Load settings
        acoustic_model = self.ppath("speech-to-text.acoustic-model", "acoustic_model")

        if open_transcription:
            # Use base dictionary/language model
            dictionary = self.ppath(
                "speech-to-text.base-dictionary", "base_dictionary.txt"
            )

            language_model = self.ppath(
                "speech-to-text.base-language-model", "base_language_model.txt"
            )

        else:
            # Use custom dictionary/language model
            dictionary = self.ppath("speech-to-text.dictionary", "dictionary.txt")

            language_model = self.ppath(
                "speech-to-text.language-model", "language_model.txt"
            )

        mllr_matrix = self.ppath(
            "speech-to-text.pocketsphinx.mllr-matrix", "mllr_matrix"
        )

        return PocketsphinxTranscriber(
            acoustic_model,
            dictionary,
            language_model,
            mllr_matrix=mllr_matrix,
            debug=debug,
        )

    def get_kaldi_transcriber(
        self, open_transcription=False, debug=False
    ) -> Union[KaldiExtensionTranscriber, KaldiCommandLineTranscriber]:
        """Create Transcriber for Kaldi."""
        # Load settings
        model_type = pydash.get(self.profile, "speech-to-text.kaldi.model-type", "")
        acoustic_model = self.ppath("speech-to-text.acoustic-model", "acoustic_model")

        if open_transcription:
            # Use base graph
            graph_dir = self.ppath("speech-to-text.kaldi.base-graph-directory") or (
                acoustic_model / "model" / "graph"
            )
        else:
            # Use custom graph
            graph_dir = self.ppath("speech-to-text.kaldi.graph-directory") or (
                acoustic_model / "graph"
            )

        if model_type == KaldiModelType.NNET3:
            _LOGGER.debug("Loading Kaldi nnet3 Python extension")

            # Use Python extension
            return KaldiExtensionTranscriber(acoustic_model, graph_dir)
        else:
            # Use kaldi-decode script
            return KaldiCommandLineTranscriber(model_type, acoustic_model, graph_dir)

    def get_julius_transcriber(
        self, open_transcription=False, debug=False
    ) -> JuliusTranscriber:
        """Create Transcriber for Julius."""
        # Load settings
        acoustic_model = self.ppath("speech-to-text.acoustic-model", "acoustic_model")

        if open_transcription:
            # Use base dictionary/language model
            dictionary = self.ppath(
                "speech-to-text.base-dictionary", "base_dictionary.txt"
            )

            language_model = self.ppath(
                "speech-to-text.base-language-model", "base_language_model.bin"
            )
        else:
            # Use custom dictionary/language model
            dictionary = self.ppath("speech-to-text.dictionary", "dictionary.txt")

            language_model = self.ppath(
                "speech-to-text.language-model", "language_model.txt"
            )

        return JuliusTranscriber(
            acoustic_model, dictionary, language_model, debug=debug
        )

    # -------------------------------------------------------------------------
    # recognize-intent
    # -------------------------------------------------------------------------

    def get_recognizer(self) -> Recognizer:
        """Create intent recognizer based on profile settings."""
        # Load settings
        intent_fst_path = self.ppath("intent-recognition.intent-fst", "intent.fst")
        stop_words_path = self.ppath("intent-recognition.stop-words", "stop_words.txt")
        fuzzy = pydash.get(self.profile, "intent-recognition.fuzzy", True)

        # Load intent finite state transducer
        intent_fst = fst.Fst.read(str(intent_fst_path))

        if fuzzy:
            # Load stop words (common words that can be safely ignored)
            stop_words: Set[str] = set()
            if (stop_words_path is not None) and stop_words_path.exists():
                stop_words.update(
                    w.strip() for w in stop_words_path.read_text().splitlines()
                )

            return FuzzyRecognizer(intent_fst, stop_words=stop_words)
        else:
            return StrictRecognizer(intent_fst)

    # -------------------------------------------------------------------------
    # Utilities
    # -------------------------------------------------------------------------

    def ppath(self, query: str, default: Optional[str] = None) -> Optional[Path]:
        """Return path from profile or path relative to the profile directory."""
        result = pydash.get(self.profile, query)
        if result is None:
            if default is not None:
                result = self.profile_dir / Path(default)
        else:
            result = Path(result)

        return result

    def convert_wav(self, wav_data: bytes) -> bytes:
        """Convert WAV data to expected audio format."""
        convert_cmd_str = pydash.get(
            self.profile,
            "audio.convert-command",
            "sox -t wav - -r 16000 -e signed-integer -b 16 -c 1 -t wav -",
        )
        convert_cmd = shlex.split(convert_cmd_str)
        _LOGGER.debug(convert_cmd)
        return subprocess.run(
            convert_cmd, check=True, stdout=subprocess.PIPE, input=wav_data
        ).stdout

    def maybe_convert_wav(self, wav_data: bytes) -> bytes:
        """Convert WAV data to expected audio format if necessary."""
        expected_rate = int(
            pydash.get(self.profile, "audio.format.sample-rate-hertz", 16000)
        )
        expected_width = (
            int(pydash.get(self.profile, "audio.format.sample-width-bits", 16)) // 8
        )
        expected_channels = int(
            pydash.get(self.profile, "audio.format.channel-count", 1)
        )

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
                    _LOGGER.debug(
                        "Got %s Hz, %s byte(s), %s channel(s). "
                        + "Needed %s Hz, %s byte(s), %s channel(s)",
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
                        _LOGGER.warning(
                            "Upsampling audio from %s to %s Hz. "
                            + "Expect poor performance!",
                            rate,
                            expected_rate,
                        )

                    return self.convert_wav(wav_data)
                else:
                    # Return original data
                    return wav_data
