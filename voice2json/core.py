"""
Core voice2json command support.
"""
import asyncio
import logging
import io
import wave
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, Union, Set, BinaryIO
import struct

import pydash

from rhasspyasr import Transcriber
from rhasspyasr_deepspeech import DeepSpeechTranscriber
from rhasspyasr_pocketsphinx import PocketsphinxTranscriber
from rhasspyasr_kaldi import (
    KaldiCommandLineTranscriber,
    train,
    get_kaldi_dir,
    KaldiModelType,
)
from rhasspysilence import VoiceCommandRecorder, VoiceCommandResult, WebRtcVadRecorder

from .train import train_profile, AcousticModelType

# from voice2json.speech.const import KaldiModelType
# from voice2json.speech import (
#     Transcriber,
#     PocketsphinxTranscriber,
#     KaldiCommandLineTranscriber,
#     KaldiExtensionTranscriber,
#     JuliusTranscriber,
# )
# from voice2json.intent import StrictRecognizer, FuzzyRecognizer
# from voice2json.intent.const import Recognizer, Recognition
# from voice2json.command.const import VoiceCommandRecorder
# from voice2json.command import WebRtcVadRecorder
# from voice2json.wake import PorcupineDetector
# from voice2json.wake.const import WakeWordDetector

_LOGGER = logging.getLogger("voice2json.core")

# -----------------------------------------------------------------------------


class Voice2JsonCore:
    """Core voice2json command support."""

    def __init__(self, profile_dir: Path, profile: Dict[str, Any], loop=None):
        """Initialize voice2json."""
        self.profile_dir = profile_dir
        self.profile = profile
        self.loop = loop or asyncio.get_event_loop()

    # -------------------------------------------------------------------------
    # train-profile
    # -------------------------------------------------------------------------

    def train_profile(self):
        """Generate speech/intent artifacts for a profile."""
        train_profile(self.profile_dir, self.profile)

    # -------------------------------------------------------------------------
    # transcribe-wav
    # -------------------------------------------------------------------------

    def get_transcriber(self, open_transcription=False, debug=False) -> Transcriber:
        """Create Transcriber based on profile speech system."""
        # Load settings
        acoustic_model_type = AcousticModelType(
            pydash.get(
                self.profile, "speech-to-text.acoustic-model-type", "pocketsphinx"
            ).lower()
        )

        if acoustic_model_type == AcousticModelType.POCKETSPHINX:
            # Pocketsphinx
            return self.get_pocketsphinx_transcriber(
                open_transcription=open_transcription, debug=debug
            )

        if acoustic_model_type == AcousticModelType.KALDI:
            # Kaldi
            return self.get_kaldi_transcriber(
                open_transcription=open_transcription, debug=debug
            )

        if acoustic_model_type == AcousticModelType.JULIUS:
            # Julius
            return self.get_julius_transcriber(
                open_transcription=open_transcription, debug=debug
            )

        if acoustic_model_type == AcousticModelType.DEEPSPEECH:
            # DeepSpeech
            return self.get_deepspeech_transcriber(
                open_transcription=open_transcription, debug=debug
            )


        raise ValueError(f"Unsupported acoustic model type: {acoustic_model_type}")

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
    ) -> KaldiCommandLineTranscriber:
        """Create Transcriber for Kaldi."""
        # Load settings
        model_type = KaldiModelType(
            pydash.get(self.profile, "speech-to-text.kaldi.model-type")
        )
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

        # Use kaldi-decode script
        return KaldiCommandLineTranscriber(model_type, acoustic_model, graph_dir)

    def get_deepspeech_transcriber(
        self, open_transcription=False, debug=False
    ) -> DeepSpeechTranscriber:
        """Create Transcriber for DeepSpeech."""
        # Load settings
        acoustic_model = self.ppath("speech-to-text.acoustic-model", "model/output_graph.pbmm")

        if open_transcription:
            # Use base model
            language_model = self.ppath("speech-to-text.deepspeech.base-language-model", "model/lm.binary")
            trie = self.ppath("speech-to-text.deepspeech.base-trie", "model/trie")
        else:
            # Use custom model
            language_model = self.ppath("speech-to-text.language-model", "lm.binary")
            trie = self.ppath("speech-to-text.deepspeech.trie", "trie")

        return DeepSpeechTranscriber(acoustic_model, language_model, trie)

    # def get_julius_transcriber(
    #     self, open_transcription=False, debug=False
    # ) -> JuliusTranscriber:
    #     """Create Transcriber for Julius."""
    #     # Load settings
    #     acoustic_model = self.ppath("speech-to-text.acoustic-model", "acoustic_model")

    #     if open_transcription:
    #         # Use base dictionary/language model
    #         dictionary = self.ppath(
    #             "speech-to-text.base-dictionary", "base_dictionary.txt"
    #         )

    #         language_model = self.ppath(
    #             "speech-to-text.base-language-model", "base_language_model.bin"
    #         )
    #     else:
    #         # Use custom dictionary/language model
    #         dictionary = self.ppath("speech-to-text.dictionary", "dictionary.txt")

    #         language_model = self.ppath(
    #             "speech-to-text.language-model", "language_model.txt"
    #         )

    #     return JuliusTranscriber(
    #         acoustic_model, dictionary, language_model, debug=debug
    #     )

    # -------------------------------------------------------------------------
    # recognize-intent
    # -------------------------------------------------------------------------

    # def get_recognizer(self) -> Recognizer:
    #     """Create intent recognizer based on profile settings."""
    #     # Load settings
    #     intent_fst_path = self.ppath("intent-recognition.intent-fst", "intent.fst")
    #     stop_words_path = self.ppath("intent-recognition.stop-words", "stop_words.txt")
    #     fuzzy = pydash.get(self.profile, "intent-recognition.fuzzy", True)

    #     # Load intent finite state transducer
    #     intent_fst = fst.Fst.read(str(intent_fst_path))

    #     if fuzzy:
    #         # Load stop words (common words that can be safely ignored)
    #         stop_words: Set[str] = set()
    #         if (stop_words_path is not None) and stop_words_path.exists():
    #             stop_words.update(
    #                 w.strip() for w in stop_words_path.read_text().splitlines()
    #             )

    #         return FuzzyRecognizer(intent_fst, stop_words=stop_words)

    #     # Use strict matching
    #     return StrictRecognizer(intent_fst)

    # -------------------------------------------------------------------------
    # record-command
    # -------------------------------------------------------------------------

    def get_command_recorder(self) -> WebRtcVadRecorder:
        """Get voice command recorder based on profile settings."""
        # # Load settings
        # vad_mode = int(pydash.get(self.profile, "voice-command.vad-mode", 3))
        # min_seconds = float(
        #     pydash.get(self.profile, "voice-command.minimum-seconds", 2)
        # )
        # max_seconds = float(
        #     pydash.get(self.profile, "voice-command.maximum-seconds", 30)
        # )
        # speech_seconds = float(
        #     pydash.get(self.profile, "voice-command.speech-seconds", 0.3)
        # )
        # silence_seconds = float(
        #     pydash.get(self.profile, "voice-command.silence-seconds", 0.5)
        # )
        # before_seconds = float(
        #     pydash.get(self.profile, "voice-command.before-seconds", 0.25)
        # )
        # chunk_size = int(pydash.get(self.profile, "voice-command.chunk-size", 960))
        # sample_rate = int(
        #     pydash.get(self.profile, "audio.format.sample-rate-hertz", 16000)
        # )

        # return WebRtcVadRecorder(
        #     vad_mode=vad_mode,
        #     sample_rate=sample_rate,
        #     chunk_size=chunk_size,
        #     min_seconds=min_seconds,
        #     max_seconds=max_seconds,
        #     speech_seconds=speech_seconds,
        #     silence_seconds=silence_seconds,
        #     before_seconds=before_seconds,
        # )

    # -------------------------------------------------------------------------
    # wait-wake
    # -------------------------------------------------------------------------

    # def get_wake_detector(self) -> WakeWordDetector:
    #     """Get wake word detector based on profile settings."""
    #     # Load settings
    #     library_path = self.ppath("wake-word.porcupine.library-file")
    #     params_path = self.ppath("wake-word.porcupine.params-file")
    #     keyword_path = self.ppath("wake-word.porcupine.keyword-file")
    #     sensitivity = float(pydash.get(self, "wake-word.sensitivity", 0.5))

    #     return PorcupineDetector(library_path, params_path, keyword_path, sensitivity)

    # -------------------------------------------------------------------------
    # test-examples
    # -------------------------------------------------------------------------

    # def test_examples(
    #     self, expected: Dict[str, Recognition], actual: Dict[str, Recognition]
    # ) -> Dict[str, Any]:
    #     """Generate report of comparison between expected and actual recognition results."""
    # # Actual intents and extra info about missing entities, etc.
    # actual_results: Dict[str, Dict[str, Any]] = {}

    # # Total number of WAV files
    # num_wavs = 0

    # # Number transcriptions that match *exactly*
    # correct_transcriptions = 0

    # # Number of words in all transcriptions (as counted by word_align.pl)
    # num_words = 0

    # # Number of correct words in all transcriptions (as computed by word_align.pl)
    # correct_words = 0

    # # Total number of intents that were attempted
    # num_intents = 0

    # # Number of recognized intents that match expectations
    # correct_intent_names = 0

    # # Number of entity/value pairs that match *exactly* in all recognized intents
    # correct_entities = 0

    # # Number of entity/value pairs all intents
    # num_entities = 0

    # # Number of intents where name and entities match exactly
    # correct_intent_and_entities = 0

    # # Real time vs transcription time
    # speedups = []

    # # Compute statistics
    # for wav_name, actual_intent in actual.items():
    #     actual_results[wav_name] = attr.asdict(actual_intent)

    #     # Get corresponding expected intent
    #     expected_intent = expected[wav_name]

    #     # Compute real-time speed-up
    #     wav_seconds = actual_intent.wav_seconds
    #     transcribe_seconds = actual_intent.transcribe_seconds
    #     if (transcribe_seconds > 0) and (wav_seconds > 0):
    #         speedups.append(wav_seconds / transcribe_seconds)

    #     # Check transcriptions
    #     actual_text = actual_intent.raw_text or actual_intent.text
    #     expected_text = expected_intent.raw_text or expected_intent.text

    #     if expected_text == actual_text:
    #         correct_transcriptions += 1

    #     # Check intents
    #     if expected_intent.intent is not None:
    #         num_intents += 1
    #         if actual_intent.intent is None:
    #             intents_match = False
    #             actual_results[wav_name]["intent"] = {"name": ""}
    #         else:
    #             intents_match = (
    #                 expected_intent.intent.name == actual_intent.intent.name
    #             )

    #         # Count entities
    #         expected_entities: List[Tuple[str, str]] = []
    #         num_expected_entities = 0
    #         for entity in expected_intent.entities:
    #             num_entities += 1
    #             num_expected_entities += 1
    #             entity_tuple = (entity.entity, entity.value)
    #             expected_entities.append(entity_tuple)

    #         # Verify actual entities.
    #         # Only check entities if intent was correct.
    #         wrong_entities = []
    #         missing_entities = []
    #         if intents_match:
    #             correct_intent_names += 1
    #             num_actual_entities = 0
    #             for entity in actual_intent.entities:
    #                 num_actual_entities += 1
    #                 entity_tuple = (entity.entity, entity.value)

    #                 if entity_tuple in expected_entities:
    #                     correct_entities += 1
    #                     expected_entities.remove(entity_tuple)
    #                 else:
    #                     wrong_entities.append(entity_tuple)

    #             # Anything left is missing
    #             missing_entities = expected_entities

    #             # Check if entities matched *exactly*
    #             if (len(expected_entities) == 0) and (
    #                 num_actual_entities == num_expected_entities
    #             ):
    #                 correct_intent_and_entities += 1

    #         actual_results[wav_name]["intent"][
    #             "expected_name"
    #         ] = expected_intent.intent.name
    #         actual_results[wav_name]["wrong_entities"] = wrong_entities
    #         actual_results[wav_name]["missing_entities"] = missing_entities

    #     num_wavs += 1

    # # ---------------------------------------------------------------------

    # if num_wavs < 1:
    #     _LOGGER.fatal("No WAV files found")
    #     sys.exit(1)

    # # Compute word error rate (WER)
    # align_results: Dict[str, Any] = {}
    # if shutil.which("word_align.pl"):
    #     from voice2json.utils import align2json

    #     with tempfile.NamedTemporaryFile(mode="w") as reference_file:
    #         # Write references
    #         for expected_key, expected_intent in expected.items():
    #             print(
    #                 expected_intent.raw_text or expected_intent.text,
    #                 f"({expected_key})",
    #                 file=reference_file,
    #             )

    #         with tempfile.NamedTemporaryFile(mode="w") as hypothesis_file:
    #             # Write hypotheses
    #             for actual_key, actual_intent in actual.items():
    #                 print(
    #                     actual_intent.raw_text or actual_intent.text,
    #                     f"({actual_key})",
    #                     file=hypothesis_file,
    #                 )

    #             # Calculate WER
    #             reference_file.seek(0)
    #             hypothesis_file.seek(0)

    #             align_cmd = [
    #                 "word_align.pl",
    #                 reference_file.name,
    #                 hypothesis_file.name,
    #             ]
    #             _LOGGER.debug(align_cmd)

    #             align_output = subprocess.check_output(align_cmd).decode()

    #             # Convert to JSON
    #             with io.StringIO(align_output) as align_file:
    #                 align_results = align2json(align_file)

    # else:
    #     _LOGGER.warn("word_align.pl not found in PATH. Not computing WER.")

    # # Merge WER results
    # for key, wer in align_results.items():
    #     actual_results[key]["word_error"] = wer
    #     num_words += wer["words"]
    #     correct_words += wer["correct"]

    # average_transcription_speedup = 0
    # if len(speedups) > 0:
    #     average_transcription_speedup = sum(speedups) / len(speedups)

    # # Summarize results
    # return {
    #     "statistics": {
    #         "num_wavs": num_wavs,
    #         "num_words": num_words,
    #         "num_entities": num_entities,
    #         "correct_transcriptions": correct_transcriptions,
    #         "correct_intent_names": correct_intent_names,
    #         "correct_words": correct_words,
    #         "correct_entities": correct_entities,
    #         "transcription_accuracy": correct_words / num_words
    #         if num_words > 0
    #         else 1,
    #         "intent_accuracy": correct_intent_names / num_intents
    #         if num_intents > 0
    #         else 1,
    #         "entity_accuracy": correct_entities / num_entities
    #         if num_entities > 0
    #         else 1,
    #         "intent_entity_accuracy": correct_intent_and_entities / num_intents
    #         if num_intents > 0
    #         else 1,
    #         "average_transcription_speedup": average_transcription_speedup,
    #     },
    #     "actual": actual_results,
    #     "expected": {
    #         wav_name: attr.asdict(intent) for wav_name, intent in expected.items()
    #     },
    # }

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
                        _LOGGER.warning(
                            "Upsampling audio from %s to %s Hz. Expect poor performance!",
                            rate,
                            expected_rate,
                        )

                    return self.convert_wav(wav_data)

                # Return original data
                return wav_data

    def buffer_to_wav(self, buffer: bytes) -> bytes:
        """Wraps a buffer of raw audio data in a WAV"""
        rate = int(pydash.get(self.profile, "audio.format.sample-rate-hertz", 16000))
        width = int(pydash.get(self.profile, "audio.format.sample-width-bits", 16)) // 8
        channels = int(pydash.get(self.profile, "audio.format.channel-count", 1))

        with io.BytesIO() as wav_buffer:
            with wave.open(wav_buffer, mode="wb") as wav_file:
                wav_file.setframerate(rate)
                wav_file.setsampwidth(width)
                wav_file.setnchannels(channels)
                wav_file.writeframesraw(buffer)

            return wav_buffer.getvalue()

    def get_audio_source(self) -> BinaryIO:
        """Start a recording subprocess for expected audio format."""
        record_cmd_str = pydash.get(
            core.profile,
            "audio.record-command",
            "arecord -q -r 16000 -c 1 -f S16_LE -t raw",
        )
        record_cmd = shlex.split(record_cmd_str)
        _LOGGER.debug(record_cmd)
        record_proc = subprocess.Popen(record_cmd, stdout=subprocess.PIPE)

        return record_proc.stdout
