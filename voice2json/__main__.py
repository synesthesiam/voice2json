"""
Command-line interface to voice2json.

For more details, see https://voice2json.org
"""

import argparse
import io
import itertools
import json
import logging
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Set, Tuple
from xml.etree import ElementTree as etree

import attr
import jsonlines
import pydash
import requests
import yaml

from voice2json.core import Voice2JsonCore
from voice2json.utils import (
    numbers_to_words,
    recursive_update,
    maybe_convert_wav,
    split_whitespace,
)

_LOGGER = logging.getLogger(__name__)


# -----------------------------------------------------------------------------


def main():
    """Called at startup."""
    yaml.SafeLoader.add_constructor("!env", env_constructor)

    # Parse command-line arguments
    args = get_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    _LOGGER.debug(args)

    # Load profile and create core
    core = get_core(args)

    # Call sub-commmand
    args.func(args, core)


# -----------------------------------------------------------------------------


def get_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(prog="voice2json", description="voice2json")
    parser.add_argument("--profile", "-p", help="Path to profle directory")
    parser.add_argument(
        "--setting",
        "-s",
        nargs=2,
        action="append",
        default=[],
        help="Override profile setting(s)",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG log to console"
    )

    sub_parsers = parser.add_subparsers()
    sub_parsers.required = True
    sub_parsers.dest = "command"

    print_parser = sub_parsers.add_parser(
        "print-profile", help="Print profile JSON to stdout"
    )
    print_parser.set_defaults(func=print_profile)

    # train-profile
    train_parser = sub_parsers.add_parser(
        "train-profile", help="Train voice2json profile"
    )
    train_parser.add_argument(
        "--db-file", help="Path to save doit DB (default: profile directory)"
    )
    train_parser.set_defaults(func=train)

    # transcribe-wav
    transcribe_parser = sub_parsers.add_parser(
        "transcribe-wav", help="Transcribe WAV file to text"
    )
    transcribe_parser.set_defaults(func=transcribe)
    transcribe_parser.add_argument(
        "--stdin-files",
        "-f",
        action="store_true",
        help="Read WAV file paths from stdin instead of WAV data",
    )
    transcribe_parser.add_argument(
        "--open",
        "-o",
        action="store_true",
        help="Use large pre-built model for transcription",
    )
    transcribe_parser.add_argument(
        "--relative-directory", help="Set wav_name as path relative to this directory"
    )
    transcribe_parser.add_argument(
        "wav_file", nargs="*", default=[], help="Path(s) to WAV file(s)"
    )
    transcribe_parser.add_argument(
        "--input-size",
        action="store_true",
        help="WAV file size is sent on a separate line for each input WAV on stdin",
    )

    # recognize-intent
    recognize_parser = sub_parsers.add_parser(
        "recognize-intent", help="Recognize intent from JSON or text"
    )
    recognize_parser.set_defaults(func=recognize)
    recognize_parser.add_argument(
        "sentence", nargs="*", default=[], help="Sentences to recognize"
    )
    recognize_parser.add_argument(
        "--text-input",
        "-t",
        action="store_true",
        help="Input is plain text instead of JSON",
    )
    recognize_parser.add_argument(
        "--replace-numbers",
        "-n",
        action="store_true",
        help="Replace numbers with words in input sentence",
    )
    recognize_parser.add_argument(
        "--perplexity",
        action="store_true",
        help="Compute perplexity of input text relative to language model",
    )

    # # record-command
    # command_parser = sub_parsers.add_parser(
    #     "record-command", help="Record voice command and write WAV to stdout"
    # )
    # command_parser.add_argument(
    #     "--audio-source", "-a", help="File to read raw 16-bit 16Khz mono audio from"
    # )
    # command_parser.add_argument(
    #     "--wav-sink", "-w", help="File to write WAV data to instead of stdout"
    # )
    # command_parser.add_argument(
    #     "--output-size",
    #     action="store_true",
    #     help="Write line with output byte count before output",
    # )
    # command_parser.set_defaults(func=record_command)

    # # wait-wake
    # wake_parser = sub_parsers.add_parser(
    #     "wait-wake", help="Listen to audio until wake word is spoken"
    # )
    # wake_parser.add_argument(
    #     "--audio-source", "-a", help="File to read raw 16-bit 16Khz mono audio from"
    # )
    # wake_parser.add_argument(
    #     "--exit-count",
    #     "-c",
    #     type=int,
    #     help="Exit after the wake word has been spoken some number of times",
    # )
    # wake_parser.set_defaults(func=wake)

    # # pronounce-word
    # pronounce_parser = sub_parsers.add_parser(
    #     "pronounce-word", help="Speak a word phonetically"
    # )
    # pronounce_parser.add_argument("word", nargs="*", help="Word(s) to prononunce")
    # pronounce_parser.add_argument(
    #     "--quiet",
    #     "-q",
    #     action="store_true",
    #     help="Don't speak word; only print phonemes",
    # )
    # pronounce_parser.add_argument(
    #     "--delay", "-d", type=float, default=0, help="Seconds to wait between words"
    # )
    # pronounce_parser.add_argument(
    #     "--nbest",
    #     "-n",
    #     type=int,
    #     default=5,
    #     help="Number of pronunciations to generate for unknown words",
    # )
    # pronounce_parser.add_argument(
    #     "--espeak", action="store_true", help="Use eSpeak even if MaryTTS is available"
    # )
    # pronounce_parser.add_argument("--wav-sink", "-w", help="File to write WAV data to")
    # pronounce_parser.add_argument(
    #     "--newline",
    #     action="store_true",
    #     help="Print a blank line after the end of each word's pronunciations",
    # )
    # pronounce_parser.set_defaults(func=pronounce)

    # # generate-examples
    # generate_parser = sub_parsers.add_parser(
    #     "generate-examples", help="Randomly generate example intents from profile"
    # )
    # generate_parser.add_argument(
    #     "--number", "-n", type=int, required=True, help="Number of examples to generate"
    # )
    # generate_parser.add_argument(
    #     "--raw-symbols",
    #     action="store_true",
    #     help="Output symbols directly from finite state transducer",
    # )
    # generate_parser.add_argument(
    #     "--iob", action="store_true", help="Output IOB format instead of JSON"
    # )
    # generate_parser.set_defaults(func=generate)

    # # record-examples
    # record_examples_parser = sub_parsers.add_parser(
    #     "record-examples",
    #     help="Randomly generate example prompts and have the user record them",
    # )
    # record_examples_parser.add_argument(
    #     "--directory",
    #     "-d",
    #     help="Directory to save recorded WAV files and transcriptions",
    # )
    # record_examples_parser.add_argument(
    #     "--audio-source", "-a", help="File to read raw 16-bit 16Khz mono audio from"
    # )
    # record_examples_parser.add_argument(
    #     "--chunk-size",
    #     type=int,
    #     default=1024,
    #     help="Number of bytes to read at a time from stdin",
    # )
    # record_examples_parser.set_defaults(func=record_examples)

    # # test-examples
    # test_examples_parser = sub_parsers.add_parser(
    #     "test-examples", help="Test performance on previously recorded examples"
    # )
    # test_examples_parser.add_argument(
    #     "--directory", "-d", help="Directory with recorded examples"
    # )
    # test_examples_parser.add_argument(
    #     "--results", "-r", help="Directory to save test results"
    # )
    # test_examples_parser.add_argument(
    #     "--expected", help="Path to jsonl file with expected test results"
    # )
    # test_examples_parser.add_argument(
    #     "--actual", help="Path to jsonl file with actual test results"
    # )
    # test_examples_parser.add_argument(
    #     "--open",
    #     "-o",
    #     action="store_true",
    #     help="Use large pre-built model for transcription",
    # )
    # test_examples_parser.set_defaults(func=test_examples)

    # # tune-examples
    # tune_examples_parser = sub_parsers.add_parser(
    #     "tune-examples", help="Tune speech recognizer with previously recorded examples"
    # )
    # tune_examples_parser.add_argument(
    #     "--directory", "-d", help="Directory with recorded examples"
    # )
    # tune_examples_parser.set_defaults(func=tune_examples)

    # # show-documentation
    # show_documentation_parser = sub_parsers.add_parser(
    #     "show-documentation", help="Run local HTTP server with documentation"
    # )
    # show_documentation_parser.add_argument(
    #     "--port",
    #     type=int,
    #     default=8000,
    #     help="Port to host web server on (default: 8000)",
    # )
    # show_documentation_parser.set_defaults(func=show_documentation)

    # # speak-sentence
    # speak_parser = sub_parsers.add_parser(
    #     "speak-sentence", help="Speak a sentence using MaryTTS"
    # )
    # speak_parser.add_argument("sentence", nargs="*", help="Sentence(s) to speak")
    # speak_parser.add_argument("--wav-sink", "-w", help="File to write WAV data to")
    # speak_parser.add_argument(
    #     "--espeak", action="store_true", help="Use eSpeak even if MaryTTS is available"
    # )
    # speak_parser.set_defaults(func=speak)

    return parser.parse_args()


# -----------------------------------------------------------------------------


def get_core(args: argparse.Namespace):
    """Load profile and create voice2json core."""
    # Load profile (YAML)
    profile_yaml: Optional[Path] = None

    if args.profile is None:
        # Guess profile location in $HOME/.config/voice2json
        if "XDG_CONFIG_HOME" in os.environ:
            config_home = Path(os.environ["XDG_CONFIG_HOME"])
        else:
            config_home = Path("~/.config").expanduser()

        profile_dir = config_home / "voice2json"
        _LOGGER.debug("Assuming profile is at %s", profile_dir)
    else:
        # Use profile provided on command line
        profile_dir_or_file = Path(args.profile)
        if profile_dir_or_file.is_dir():
            # Assume directory with profile.yaml
            profile_dir = profile_dir_or_file
        else:
            # Assume YAML file
            profile_dir = profile_dir_or_file.parent
            profile_yaml = profile_dir_or_file

    # Set environment variable usually referenced in profile
    profile_dir = profile_dir.resolve()
    os.environ["profile_dir"] = str(profile_dir)

    # x86_64, armv7l, armv6l, ...
    os.environ["machine"] = platform.machine()

    # Load profile defaults
    defaults_yaml = (
        Path(os.environ.get("voice2json_dir", os.getcwd()))
        / "etc"
        / "profile.defaults.yml"
    )
    if defaults_yaml.exists():
        _LOGGER.debug("Loading profile defaults from %s", defaults_yaml)
        with open(defaults_yaml, "r") as defaults_file:
            profile = yaml.safe_load(defaults_file)
    else:
        # No defaults
        profile = {}

    # Load profile
    if profile_yaml is None:
        profile_yaml = profile_dir / "profile.yml"

    _LOGGER.debug("Loading profile from %s", profile_yaml)

    if profile_yaml.exists():
        os.environ["profile_file"] = str(profile_yaml)

        with open(profile_yaml, "r") as profile_file:
            recursive_update(profile, yaml.safe_load(profile_file) or {})
    else:
        _LOGGER.warning("%s does not exist. Using default settings.", profile_yaml)

    # Override settings
    for setting_path, setting_value in args.setting:
        setting_value = json.loads(setting_value)
        _LOGGER.debug("Overriding %s with %s", setting_path, setting_value)
        pydash.set_(profile, setting_path, setting_value)

    # Create core
    return Voice2JsonCore(profile_dir, profile)


# -----------------------------------------------------------------------------


def print_profile(args: argparse.Namespace, core: Voice2JsonCore) -> None:
    """Print all settings as JSON."""
    json.dump(core.profile, sys.stdout, indent=4)


# -----------------------------------------------------------------------------


def train(args: argparse.Namespace, core: Voice2JsonCore) -> None:
    """Create speech/intent artifacts for a profile."""
    core.train_profile(db_path=args.db_file)


# -----------------------------------------------------------------------------


def transcribe(args: argparse.Namespace, core: Voice2JsonCore) -> None:
    """Speech to text from WAV file(s)."""

    # Make sure profile has been trained
    check_trained(core)

    # Get speech to text transcriber for profile
    transcriber = core.get_transcriber(open_transcription=args.open, debug=args.debug)

    # Directory to report WAV file names relative to
    relative_dir = (
        None if args.relative_directory is None else Path(args.relative_directory)
    )

    try:
        if (len(args.wav_file) > 0) or args.stdin_files:
            # Read WAV file paths
            wav_files = args.wav_file
            if args.stdin_files:
                _LOGGER.debug("Reading file paths from stdin")
                wav_files = itertools.chain(wav_files, sys.stdin)

            for wav_path_str in wav_files:
                wav_path_str = wav_path_str.strip()

                # Load and convert
                wav_path = Path(wav_path_str)
                _LOGGER.debug("Transcribing %s", wav_path)

                wav_data = core.maybe_convert_wav(wav_path.read_bytes())

                # Transcribe
                transcription = transcriber.transcribe_wav(wav_data)
                result = attr.asdict(transcription)

                if relative_dir is None:
                    # Add name of WAV file to result
                    result["wav_name"] = wav_path.name
                else:
                    # Make relative to some directory
                    result["wav_name"] = str(wav_path.relative_to(relative_dir))

                print_json(result)
        else:
            # Read WAV data from stdin
            _LOGGER.debug("Reading WAV data from stdin")

            if args.input_size:
                # Number of bytes is on separate line
                line = sys.stdin.buffer.readline().strip()
                if len(line) == 0:
                    return

                num_bytes = int(line)
                while num_bytes > 0:
                    # Read in WAV
                    wav_data = sys.stdin.buffer.read(num_bytes)
                    while len(wav_data) < num_bytes:
                        wav_data = sys.stdin.buffer.read(num_bytes - len(wav_data))

                    # Transcribe
                    wav_data = core.maybe_convert_wav(wav_data)
                    transcription = transcriber.transcribe_wav(wav_data)
                    result = attr.asdict(transcription)

                    print_json(result)

                    # Next WAV
                    line = sys.stdin.buffer.readline().strip()
                    if len(line) == 0:
                        break

                    num_bytes = int(line)
            else:
                # Load and convert entire input
                wav_data = core.maybe_convert_wav(sys.stdin.buffer.read())

                # Transcribe
                transcription = transcriber.transcribe_wav(wav_data)
                result = attr.asdict(transcription)

                print_json(result)
    except KeyboardInterrupt:
        pass
    finally:
        transcriber.stop()


# -----------------------------------------------------------------------------


def recognize(args: argparse.Namespace, core: Voice2JsonCore) -> None:
    """Recognize intent from sentence(s)."""
    # Make sure profile has been trained
    check_trained(core)

    # Load settings
    language_code = pydash.get(core.profile, "language.code", "en-US")
    word_casing = pydash.get(core.profile, "training.word-casing", "ignore").lower()
    skip_unknown = pydash.get(core.profile, "intent-recognition.skip_unknown", True)

    # Load intent recognizer
    recognizer = core.get_recognizer()

    # Ignore words outside of input symbol table
    known_tokens: Optional[Set[str]] = None
    if skip_unknown:
        known_tokens = set()
        in_symbols = recognizer.intent_fst.input_symbols()
        for i in range(in_symbols.num_symbols()):
            key = in_symbols.get_nth_key(i)
            token = in_symbols.find(i).decode()

            # Exclude meta tokens and <eps>
            if not (token.startswith("__") or token.startswith("<")):
                known_tokens.add(token)

    # Build up sentence transformer
    def identity(x):
        return x

    sentence_transform = identity

    if word_casing == "upper":
        sentence_transform = str.upper
    elif word_casing == "lower":
        sentence_transform = str.lower

    if args.replace_numbers:
        old_transform = sentence_transform

        def number_transform(s):
            # Automatically convert numbers to words
            return numbers_to_words(old_transform(s), language=language_code)

        sentence_transform = number_transform

    if len(args.sentence) > 0:
        sentences = args.sentence
    else:
        _LOGGER.debug("Reading sentences from stdin")
        sentences = sys.stdin

    # Process sentences
    try:
        for sentence in sentences:
            if args.text_input:
                # Input is plain text
                text = sentence
                sentence_object = {"text": text}
            else:
                # Input is JSON
                sentence_object = json.loads(sentence)
                text = sentence_object.get("text", "")

            # Tokenize
            text = text.strip()
            tokens = split_whitespace(text)

            if known_tokens is not None:
                # Filter tokens
                known_tokens = [t for t in tokens if t in known_tokens]

            # Recognize intent
            recognition = recognizer.recognize(tokens)
            result = attr.asdict(recognition)

            if args.perplexity:
                try:
                    # Compute sentence perplexity with ngramperplexity
                    with tempfile.TemporaryDirectory() as temp_dir_name:
                        temp_path = Path(temp_dir_name)
                        text_path = temp_path / "sentence.txt"
                        text_path.write_text(text)

                        symbols_path = temp_path / "sentence.syms"
                        subprocess.check_call(
                            ["ngramsymbols", str(text_path), str(symbols_path)]
                        )

                        far_path = temp_path / "sentence.far"
                        subprocess.check_call(
                            [
                                "farcompilestrings",
                                f"-symbols={symbols_path}",
                                "-keep_symbols=1",
                                str(text_path),
                                str(far_path),
                            ]
                        )

                        verbosity = 1 if args.debug else 0
                        output = subprocess.check_output(
                            [
                                "ngramperplexity",
                                f"--v={verbosity}",
                                str(core.profile_dir / "intent.fst.model"),
                                str(far_path),
                            ]
                        ).decode()

                        _LOGGER.debug(output)

                        last_line = output.strip().splitlines()[-1]
                        perplexity = float(
                            re.match(r"^.*perplexity\s*=\s*(.+)$", last_line).group(1)
                        )
                        result["perplexity"] = perplexity
                except Exception:
                    _LOGGER.exception("perplexity")

            # Merge with input object
            for key, value in result.items():
                sentence_object[key] = value

            print_json(sentence_object)
    except KeyboardInterrupt:
        pass


# # -----------------------------------------------------------------------------


# def record_command(
#     args: argparse.Namespace, profile_dir: Path, profile: Dict[str, Any]
# ) -> None:
#     from voice2json.command.webrtcvad import wait_for_command
#     from voice2json.utils import buffer_to_wav, get_audio_source

#     # Make sure profile has been trained
#     check_trained(profile, profile_dir)

#     # Load settings
#     vad_mode = int(pydash.get(profile, "voice-command.vad-mode", 3))
#     min_seconds = float(pydash.get(profile, "voice-command.minimum-seconds", 2))
#     max_seconds = float(pydash.get(profile, "voice-command.maximum-seconds", 30))
#     speech_seconds = float(pydash.get(profile, "voice-command.speech-seconds", 0.3))
#     silence_seconds = float(pydash.get(profile, "voice-command.silence-seconds", 0.5))
#     before_seconds = float(pydash.get(profile, "voice-command.before-seconds", 0.25))

#     # Expecting raw 16-bit, 16Khz mono audio
#     if args.audio_source is None:
#         audio_source = get_audio_source(profile)
#         _LOGGER.debug("Recording raw 16-bit 16Khz mono audio")
#     elif args.audio_source == "-":
#         # Avoid crash when stdin is closed/read in daemon thread
#         class FakeStdin:
#             def __init__(self):
#                 self.done = False

#             def read(self, n):
#                 if self.done:
#                     return None

#                 return sys.stdin.buffer.read(n)

#             def close(self):
#                 self.done = True

#         audio_source = FakeStdin()
#         _LOGGER.debug("Recording raw 16-bit 16Khz mono audio from stdin")
#     else:
#         audio_source: BinaryIO = open(args.audio_source, "rb")
#         _LOGGER.debug("Recording raw 16-bit 16Khz mono audio from %s", args.audio_source)

#     # JSON events are not printed by default
#     json_file = None
#     wav_sink = sys.stdout.buffer

#     if (args.wav_sink is not None) and (args.wav_sink != "-"):
#         wav_sink = open(args.wav_sink, "wb")

#         # Print JSON to stdout
#         json_file = sys.stdout

#     # Record command
#     audio_buffer = wait_for_command(
#         audio_source,
#         vad_mode=vad_mode,
#         min_seconds=min_seconds,
#         max_seconds=max_seconds,
#         speech_seconds=speech_seconds,
#         silence_seconds=silence_seconds,
#         before_seconds=before_seconds,
#         json_file=json_file,
#     )

#     # Output WAV data
#     wav_bytes = buffer_to_wav(profile, audio_buffer)

#     if args.output_size:
#         size_str = str(len(wav_bytes)) + "\n"
#         wav_sink.write(size_str.encode())

#     wav_sink.write(wav_bytes)


# # -----------------------------------------------------------------------------


# def wake(args: argparse.Namespace, profile_dir: Path, profile: Dict[str, Any]) -> None:
#     import struct
#     from voice2json.utils import get_audio_source
#     from voice2json.wake.porcupine import Porcupine

#     # Load settings
#     library_path = ppath(profile, profile_dir, "wake-word.porcupine.library-file")
#     params_path = ppath(profile, profile_dir, "wake-word.porcupine.params-file")
#     keyword_path = ppath(profile, profile_dir, "wake-word.porcupine.keyword-file")
#     sensitivity = float(pydash.get(profile, "wake-word.sensitivity", 0.5))

#     # Load porcupine
#     handle = Porcupine(
#         str(library_path),
#         str(params_path),
#         keyword_file_paths=[str(keyword_path)],
#         sensitivities=[sensitivity],
#     )

#     chunk_size = handle.frame_length * 2
#     chunk_format = "h" * handle.frame_length

#     # Expecting raw 16-bit, 16Khz mono audio
#     if args.audio_source is None:
#         audio_source = get_audio_source(profile)
#         _LOGGER.debug("Recording raw 16-bit 16Khz mono audio")
#     elif args.audio_source == "-":
#         audio_source = sys.stdin.buffer
#         _LOGGER.debug("Recording raw 16-bit 16Khz mono audio from stdin")
#     else:
#         audio_source: BinaryIO = open(args.audio_source, "rb")
#         _LOGGER.debug("Recording raw 16-bit 16Khz mono audio from %s", args.audio_source)

#     # Read first audio chunk
#     start_time = time.time()
#     chunk = audio_source.read(chunk_size)

#     try:
#         while len(chunk) == chunk_size:
#             # Process audio chunk
#             unpacked_chunk = struct.unpack_from(chunk_format, chunk)
#             keyword_index = handle.process(unpacked_chunk)

#             if keyword_index:
#                 result = {
#                     "keyword": str(keyword_path),
#                     "detect_seconds": time.time() - start_time,
#                 }
#                 print_json(result)

#                 # Check exit count
#                 if args.exit_count is not None:
#                     args.exit_count -= 1
#                     if args.exit_count <= 0:
#                         break

#             # Get next chunk
#             chunk = audio_source.read(chunk_size)
#     except KeyboardInterrupt:
#         pass  # expected


# # -----------------------------------------------------------------------------


# def pronounce(
#     args: argparse.Namespace, profile_dir: Path, profile: Dict[str, Any]
# ) -> None:
#     from voice2json.utils import read_dict

#     # Make sure profile has been trained
#     check_trained(profile, profile_dir)

#     base_dictionary_path = ppath(
#         profile, profile_dir, "training.base_dictionary", "base_dictionary.txt"
#     )
#     dictionary_path = ppath(
#         profile, profile_dir, "training.dictionary", "dictionary.txt"
#     )
#     custom_words_path = ppath(
#         profile, profile_dir, "training.custom-words-file", "custom_words.txt"
#     )
#     g2p_path = ppath(profile, profile_dir, "training.g2p-model", "g2p.fst")
#     g2p_exists = g2p_path.exists()

#     play_command = shlex.split(pydash.get(profile, "audio.play-command"))

#     word_casing = pydash.get(profile, "training.word-casing", "ignore").lower()

#     # True if audio will go to stdout.
#     # In this case, printing will go to stderr.
#     wav_stdout = args.wav_sink == "-"

#     print_file = sys.stderr if wav_stdout else sys.stdout

#     # Load dictionaries
#     dictionary_paths = [dictionary_path, base_dictionary_path]

#     if custom_words_path.exists():
#         dictionary_paths.insert(0, custom_words_path)

#     pronunciations: Dict[str, List[str]] = defaultdict(list)

#     for dict_path in dictionary_paths:
#         if dict_path.exists():
#             with open(dict_path, "r") as dict_file:
#                 read_dict(dict_file, pronunciations)

#     # Load text to speech system
#     marytts_voice = pydash.get(profile, "text-to-speech.marytts.voice")
#     marytts_proc = None

#     if not args.quiet:
#         if args.espeak or (marytts_voice is None):
#             # Use eSpeak
#             espeak_voice = pydash.get(profile, "text-to-speech.espeak.voice")
#             espeak_map_path = ppath(
#                 profile,
#                 profile_dir,
#                 "text-to-speech.espeak.phoneme-map",
#                 "espeak_phonemes.txt",
#             )

#             if not espeak_map_path.exists():
#                 _LOGGER.fatal(
#                     f"Missing eSpeak phoneme map (expected at {espeak_map_path})"
#                 )
#                 sys.exit(1)

#             espeak_phoneme_map = dict(
#                 re.split(r"\s+", line.strip(), maxsplit=1)
#                 for line in espeak_map_path.read_text().splitlines()
#             )

#             espeak_cmd_format = pydash.get(
#                 profile, "text-to-speech.espeak.pronounce-command"
#             )

#             def do_pronounce(word, dict_phonemes):
#                 espeak_phonemes = [espeak_phoneme_map[p] for p in dict_phonemes]
#                 espeak_str = "".join(espeak_phonemes)
#                 espeak_cmd = shlex.split(espeak_cmd_format.format(phonemes=espeak_str))

#                 if espeak_voice is not None:
#                     espeak_cmd.extend(["-v", str(espeak_voice)])

#                 _LOGGER.debug(espeak_cmd)
#                 return subprocess.check_output(espeak_cmd)

#         else:
#             # Use MaryTTS
#             marytts_map_path = ppath(
#                 profile,
#                 profile_dir,
#                 "text-to-speech.marytts.phoneme-map",
#                 "marytts_phonemes.txt",
#             )

#             if not marytts_map_path.exists():
#                 _LOGGER.fatal(
#                     f"Missing MaryTTS phoneme map (expected at {marytts_map_path})"
#                 )
#                 sys.exit(1)

#             marytts_phoneme_map = dict(
#                 re.split(r"\s+", line.strip(), maxsplit=1)
#                 for line in marytts_map_path.read_text().splitlines()
#             )

#             # End of sentence token
#             sentence_end = pydash.get(
#                 profile, "text-to-speech.marytts.sentence-end", ""
#             )

#             # Rate of pronunciation
#             pronounce_rate = str(
#                 pydash.get(profile, "text-to-speech.marytts.pronounce-rate", "5%")
#             )

#             # Start MaryTTS server
#             marytts_proc, url, params = start_marytts(
#                 args, profile_dir, profile, marytts_voice
#             )

#             def do_pronounce(word, dict_phonemes):
#                 marytts_phonemes = [marytts_phoneme_map[p] for p in dict_phonemes]
#                 phoneme_str = " ".join(marytts_phonemes)
#                 _LOGGER.debug(phoneme_str)

#                 # Construct MaryXML input
#                 params["INPUT_TYPE"] = "RAWMARYXML"
#                 mary_xml = etree.fromstring(
#                     """<?xml version="1.0" encoding="UTF-8"?>
#                 <maryxml version="0.5" xml:lang="en-US">
#                 <p><prosody rate="100%"><s><phrase></phrase></s></prosody></p>
#                 </maryxml>"""
#                 )

#                 s = mary_xml.getchildren()[0]
#                 p = s.getchildren()[0]
#                 p.attrib["rate"] = pronounce_rate

#                 phrase = p.getchildren()[0]
#                 t = etree.SubElement(phrase, "t", attrib={"ph": phoneme_str})
#                 t.text = word

#                 if len(sentence_end) > 0:
#                     # Add end of sentence token
#                     eos = etree.SubElement(phrase, "t", attrib={"pos": "."})
#                     eos.text = sentence_end

#                 # Serialize XML
#                 with io.BytesIO() as xml_file:
#                     etree.ElementTree(mary_xml).write(
#                         xml_file, encoding="utf-8", xml_declaration=True
#                     )

#                     xml_data = xml_file.getvalue()
#                     _LOGGER.debug(xml_data)
#                     params["INPUT_TEXT"] = xml_data

#                 result = requests.get(url, params=params)
#                 _LOGGER.debug(result)

#                 if result.ok:
#                     return result.content
#                 else:
#                     # Not sure what to do here
#                     return bytes()

#     else:
#         # Quiet
#         def do_pronounce(word, dict_phonemes):
#             pass

#     # -------------------------------------------------------------------------

#     if len(args.word) > 0:
#         words = args.word
#     else:
#         words = sys.stdin

#     # Process words
#     try:
#         for word in words:
#             word_parts = re.split(r"\s+", word.strip())
#             word = word_parts[0]
#             dict_phonemes = []

#             if word_casing == "upper":
#                 word = word.upper()
#             elif word_casing == "lower":
#                 word = word.lower()

#             if len(word_parts) > 1:
#                 # Pronunciation provided
#                 dict_phonemes.append(word_parts[1:])

#             if word in pronunciations:
#                 # Use pronunciations from dictionary
#                 dict_phonemes.extend(re.split(r"\s+", p) for p in pronunciations[word])
#             elif g2p_exists:
#                 # Don't guess if a pronunciation was provided
#                 if len(dict_phonemes) == 0:
#                     # Guess pronunciation with phonetisaurus
#                     _LOGGER.debug("Guessing pronunciation for %s", word)

#                     with tempfile.NamedTemporaryFile(mode="w") as word_file:
#                         print(word, file=word_file)
#                         word_file.seek(0)

#                         phonetisaurus_cmd = [
#                             "phonetisaurus-apply",
#                             "--model",
#                             str(g2p_path),
#                             "--word_list",
#                             word_file.name,
#                             "--nbest",
#                             str(args.nbest),
#                         ]

#                         _LOGGER.debug(phonetisaurus_cmd)
#                         output_lines = (
#                             subprocess.check_output(phonetisaurus_cmd)
#                             .decode()
#                             .splitlines()
#                         )
#                         dict_phonemes.extend(
#                             re.split(r"\s+", line.strip())[1:] for line in output_lines
#                         )
#             else:
#                 _LOGGER.warn(f"No pronunciation for {word}")

#             # Avoid duplicate pronunciations
#             used_pronunciations: Set[str] = set()

#             for phonemes in dict_phonemes:
#                 phoneme_str = " ".join(phonemes)
#                 if phoneme_str in used_pronunciations:
#                     continue

#                 print(word, phoneme_str, file=print_file)
#                 print_file.flush()

#                 used_pronunciations.add(phoneme_str)

#                 if not args.quiet:
#                     # Speak with espeak or MaryTTS
#                     wav_data = do_pronounce(word, phonemes)

#                     if args.wav_sink is not None:
#                         # Write WAV output somewhere
#                         if args.wav_sink == "-":
#                             # STDOUT
#                             wav_sink = sys.stdout.buffer
#                         else:
#                             # File output
#                             wav_sink = open(args.wav_sink, "wb")

#                         wav_sink.write(wav_data)
#                         wav_sink.flush()
#                     else:
#                         # Play audio directly
#                         _LOGGER.debug(play_command)
#                         subprocess.run(play_command, input=wav_data, check=True)

#                     # Delay before next word
#                     time.sleep(args.delay)

#             if args.newline:
#                 print("", file=print_file)
#                 print_file.flush()

#     except KeyboardInterrupt:
#         pass
#     finally:
#         if marytts_proc is not None:
#             # Stop MaryTTS server
#             marytts_proc.terminate()
#             marytts_proc.wait()


# # -----------------------------------------------------------------------------


# def generate(
#     args: argparse.Namespace, profile_dir: Path, profile: Dict[str, Any]
# ) -> None:
#     import pywrapfst as fst
#     from voice2json.train.jsgf2fst import fstprintall, symbols2intent

#     # Make sure profile has been trained
#     check_trained(profile, profile_dir)

#     # Load settings
#     intent_fst_path = ppath(
#         profile, profile_dir, "intent-recognition.intent-fst", "intent.fst"
#     )

#     # Load intent finite state transducer
#     intent_fst = fst.Fst.read(str(intent_fst_path))

#     if args.number <= 0:
#         # Generatel all possible examples
#         rand_fst = intent_fst
#     else:
#         # Generate samples
#         rand_fst = fst.randgen(intent_fst, npath=args.number)

#     # Convert to words/tokens
#     for symbols in fstprintall(rand_fst, exclude_meta=False):
#         if args.raw_symbols:
#             print(" ".join(symbols))
#             continue

#         # Convert to intent
#         intent = symbols2intent(symbols)

#         # Add slots
#         intent["slots"] = {}
#         for ev in intent["entities"]:
#             intent["slots"][ev["entity"]] = ev["value"]

#         if args.iob:
#             # IOB format
#             token_idx = 0
#             entity_start = {ev["start"]: ev for ev in intent["entities"]}
#             entity_end = {ev["end"]: ev for ev in intent["entities"]}
#             entity = None

#             word_tags = []
#             for word in intent["tokens"]:
#                 # Determine tag label
#                 tag = "O" if not entity else f"I-{entity}"
#                 if token_idx in entity_start:
#                     entity = entity_start[token_idx]["entity"]
#                     tag = f"B-{entity}"

#                 word_tags.append((word, tag))

#                 # word ner
#                 token_idx += len(word) + 1

#                 if (token_idx - 1) in entity_end:
#                     entity = None

#             print("BS", end=" ")
#             for wt in word_tags:
#                 print(wt[0], end=" ")
#             print("ES", end="\t")

#             print("O", end=" ")  # BS
#             for wt in word_tags:
#                 print(wt[1], end=" ")
#             print("O", end="\t")  # ES

#             # Intent name last
#             print(intent["intent"]["name"])
#         else:
#             # Write as jsonl
#             print_json(intent)


# # -----------------------------------------------------------------------------


# def record_examples(
#     args: argparse.Namespace, profile_dir: Path, profile: Dict[str, Any]
# ) -> None:
#     import pywrapfst as fst
#     from voice2json.utils import buffer_to_wav, get_audio_source
#     from voice2json.train.jsgf2fst import fstprintall, symbols2intent

#     # Make sure profile has been trained
#     check_trained(profile, profile_dir)

#     chunk_size = args.chunk_size
#     examples_dir = Path(args.directory) if args.directory is not None else Path.cwd()
#     examples_dir.mkdir(parents=True, exist_ok=True)

#     # Load settings
#     intent_fst_path = ppath(
#         profile, profile_dir, "intent-recognition.intent-fst", "intent.fst"
#     )

#     # Load intent finite state transducer
#     intent_fst = fst.Fst.read(str(intent_fst_path))

#     def generate_intent() -> Dict[str, Any]:
#         # Generate sample sentence
#         rand_fst = fst.randgen(intent_fst, npath=1)

#         # Convert to words/tokens
#         symbols = fstprintall(rand_fst, exclude_meta=False)[0]

#         # Convert to intent
#         return symbols2intent(symbols)

#     def get_wav_path(text: str, count: int) -> Path:
#         # /dir/the_transcription_text-000.wav
#         text = re.sub(r"\s+", "_", text)
#         return examples_dir / f"{text}-{count:03d}.wav"

#     # Expecting raw 16-bit, 16Khz mono audio
#     if args.audio_source is None:
#         audio_source = get_audio_source(profile)
#         _LOGGER.debug("Recording raw 16-bit 16Khz mono audio")
#     elif args.audio_source == "-":
#         audio_source = sys.stdin.buffer
#         _LOGGER.debug("Recording raw 16-bit 16Khz mono audio from stdin")
#     else:
#         audio_source: BinaryIO = open(args.audio_source, "rb")
#         _LOGGER.debug("Recording raw 16-bit 16Khz mono audio from %s", args.audio_source)

#     # Recording thread
#     audio_data = bytes()
#     recording = False

#     def record_audio():
#         nonlocal audio_source, recording, audio_data
#         while audio_source is not None:
#             chunk = audio_source.read(chunk_size)
#             if recording:
#                 audio_data += chunk

#     record_thread = threading.Thread(target=record_audio, daemon=True)
#     record_thread.start()

#     try:
#         while True:
#             # Generate random intent for prompt
#             random_intent = generate_intent()
#             text = random_intent["text"]

#             # Prompt
#             print("---")
#             print(text)

#             # Instructions
#             print("Press ENTER to start recording (CTRL+C to exit)")
#             input()

#             # Record
#             audio_data = bytes()
#             recording = True

#             # Instructions
#             print("Recording from audio source. Press ENTER to stop (CTRL+C to exit).")
#             input()

#             # Save WAV
#             recording = False
#             logging.debug(f"Recorded {len(audio_data)} byte(s) of audio data")

#             count = 0
#             wav_path = get_wav_path(text, count)
#             while wav_path.exists():
#                 # Find unique name
#                 count += 1
#                 wav_path = get_wav_path(text, count)

#             wav_bytes = buffer_to_wav(profile, audio_data)
#             wav_path.write_bytes(wav_bytes)

#             # Save transcription
#             transcript_path = examples_dir / f"{wav_path.stem}.txt"
#             transcript_path.write_text(text)

#             # Save intent
#             intent_path = examples_dir / f"{wav_path.stem}.json"
#             with open(intent_path, "w") as intent_file:
#                 with jsonlines.Writer(intent_file) as out:
#                     out.write(random_intent)

#             # Response
#             print("Wrote", wav_path)
#             print("")

#     except KeyboardInterrupt:
#         audio_source = None
#         record_thread.join()


# # -----------------------------------------------------------------------------


# def _get_actual_results(
#     args: argparse.Namespace, profile_dir: Path, profile: Dict[str, Any]
# ):
#     from voice2json import get_transcriber, get_recognizer

#     examples_dir = Path(args.directory) if args.directory is not None else Path.cwd()
#     _LOGGER.debug("Looking for examples in %s", examples_dir)

#     # Load WAV transcriber
#     transcriber = get_transcriber(
#         profile_dir, profile, debug=args.debug, open_transcription=args.open
#     )

#     # Intent recognizer
#     recognizer = get_recognizer(profile_dir, profile)

#     # Process examples
#     actual: Dict[str, Dict[str, Any]] = {}
#     try:
#         for wav_path in examples_dir.glob("*.wav"):
#             _LOGGER.debug("Processing %s", wav_path)

#             # Transcribe WAV
#             wav_data = wav_path.read_bytes()
#             actual_transcription = transcriber.transcribe_wav(wav_data)
#             actual_text = actual_transcription.get(
#                 "raw_text", actual_transcription["text"]
#             )
#             _LOGGER.debug(actual_text)

#             # Do recognition
#             if recognizer is None:
#                 # Load recognizer on demand
#                 recognizer = get_recognizer(profile_dir, profile)

#             actual_intent = recognizer.recognize(actual_text)

#             # Merge with transcription
#             for key, value in actual_transcription.items():
#                 if key not in actual_intent:
#                     actual_intent[key] = value

#             _LOGGER.debug(actual_intent)

#             # Record full intent
#             actual[wav_path.name] = actual_intent
#     finally:
#         transcriber.stop()

#     return actual


# def test_examples(
#     args: argparse.Namespace, profile_dir: Path, profile: Dict[str, Any]
# ) -> None:
#     # Make sure profile has been trained
#     check_trained(profile, profile_dir)

#     results_dir = None
#     if args.results is not None:
#         results_dir = Path(args.results)

#     # Expected/actual intents
#     expected: Dict[str, Dict[str, Any]] = {}
#     actual: Dict[str, Dict[str, Any]] = {}

#     if args.expected is None:
#         examples_dir = (
#             Path(args.directory) if args.directory is not None else Path.cwd()
#         )

#         # Load expected transcriptions/intents from examples directory
#         _LOGGER.debug("Loading expected transcriptions/intents")
#         for wav_path in examples_dir.glob("*.wav"):
#             # Load expected intent (optional)
#             intent_path = examples_dir / f"{wav_path.stem}.json"
#             expected_intent = None
#             if intent_path.exists():
#                 with open(intent_path, "r") as intent_file:
#                     expected_intent = json.load(intent_file)
#             else:
#                 # Load expected transcription only
#                 transcript_path = examples_dir / f"{wav_path.stem}.txt"
#                 if transcript_path.exists():
#                     # Use text only
#                     expected_text = transcript_path.read_text().strip()
#                     expected_intent = {"text": expected_text}

#             if expected_intent is None:
#                 _LOGGER.warn(f"Skipping {wav_path} (no transcription or intent files)")
#                 continue

#             expected[wav_path.name] = expected_intent
#     else:
#         # Load expected results from jsonl file
#         with open(args.expected, "r") as expected_file:
#             for line in expected_file:
#                 expected_intent = json.loads(line)
#                 wav_name = expected_intent["wav_name"]
#                 expected[wav_name] = expected_intent

#     if args.actual is None:
#         # Do transcription/recognition
#         actual = _get_actual_results(args, profile_dir, profile)
#     else:
#         # Load actual results from jsonl file
#         with open(args.actual, "r") as actual_file:
#             for line in actual_file:
#                 actual_intent = json.loads(line)
#                 wav_name = actual_intent["wav_name"]
#                 actual[wav_name] = actual_intent

#     # ----------
#     # Statistics
#     # ----------

#     # Total number of WAV files
#     num_wavs = 0

#     # Number transcriptions that match *exactly*
#     correct_transcriptions = 0

#     # Number of words in all transcriptions (as counted by word_align.pl)
#     num_words = 0

#     # Number of correct words in all transcriptions (as computed by word_align.pl)
#     correct_words = 0

#     # Total number of intents that were attempted
#     num_intents = 0

#     # Number of recognized intents that match expectations
#     correct_intent_names = 0

#     # Number of entity/value pairs that match *exactly* in all recognized intents
#     correct_entities = 0

#     # Number of entity/value pairs all intents
#     num_entities = 0

#     # Number of intents where name and entities match exactly
#     correct_intent_and_entities = 0

#     # Real time vs transcription time
#     speedups = []

#     # Compute statistics
#     for wav_name, actual_intent in actual.items():
#         expected_intent = expected[wav_name]

#         wav_seconds = actual_intent.get("wav_seconds", 0)
#         transcribe_seconds = actual_intent.get("transcribe_seconds", 0)
#         if (transcribe_seconds > 0) and (wav_seconds > 0):
#             speedups.append(wav_seconds / transcribe_seconds)

#         # Check transcriptions
#         actual_text = actual_intent.get("raw_text", actual_intent.get("text", ""))
#         expected_text = expected_intent.get("raw_text", expected_intent.get("text", ""))

#         if expected_text == actual_text:
#             correct_transcriptions += 1

#         # Check intents
#         if "intent" in expected_intent:
#             num_intents += 1
#             intents_match = (
#                 expected_intent["intent"]["name"] == actual_intent["intent"]["name"]
#             )

#             # Count entities
#             expected_entities: List[Tuple[str, str]] = []
#             num_expected_entities = 0
#             for entity_dict in expected_intent.get("entities", []):
#                 num_entities += 1
#                 num_expected_entities += 1
#                 entity_tuple = (entity_dict["entity"], entity_dict["value"])
#                 expected_entities.append(entity_tuple)

#             # Verify actual entities.
#             # Only check entities if intent was correct.
#             wrong_entities = []
#             missing_entities = []
#             if intents_match:
#                 correct_intent_names += 1
#                 num_actual_entities = 0
#                 for entity_dict in actual_intent.get("entities", []):
#                     num_actual_entities += 1
#                     entity_tuple = (entity_dict["entity"], entity_dict["value"])

#                     if entity_tuple in expected_entities:
#                         correct_entities += 1
#                         expected_entities.remove(entity_tuple)
#                     else:
#                         wrong_entities.append(entity_tuple)

#                 # Anything left is missing
#                 missing_entities = expected_entities

#                 # Check if entities matched *exactly*
#                 if (len(expected_entities) == 0) and (
#                     num_actual_entities == num_expected_entities
#                 ):
#                     correct_intent_and_entities += 1

#             actual_intent["intent"]["expected_name"] = expected_intent["intent"]["name"]
#             actual_intent["wrong_entities"] = wrong_entities
#             actual_intent["missing_entities"] = missing_entities

#         num_wavs += 1

#     # ---------------------------------------------------------------------

#     if num_wavs < 1:
#         _LOGGER.fatal("No WAV files found")
#         sys.exit(1)

#     # Compute word error rate (WER)
#     align_results: Dict[str, Any] = {}
#     if shutil.which("word_align.pl"):
#         from voice2json.utils import align2json

#         with tempfile.NamedTemporaryFile(mode="w") as reference_file:
#             # Write references
#             for expected_key, expected_intent in expected.items():
#                 print(
#                     expected_intent.get("raw_text", expected_intent["text"]),
#                     f"({expected_key})",
#                     file=reference_file,
#                 )

#             with tempfile.NamedTemporaryFile(mode="w") as hypothesis_file:
#                 # Write hypotheses
#                 for actual_key, actual_intent in actual.items():
#                     print(
#                         actual_intent.get("raw_text", actual_intent["text"]),
#                         f"({actual_key})",
#                         file=hypothesis_file,
#                     )

#                 # Calculate WER
#                 reference_file.seek(0)
#                 hypothesis_file.seek(0)

#                 align_cmd = ["word_align.pl", reference_file.name, hypothesis_file.name]
#                 _LOGGER.debug(align_cmd)

#                 align_output = subprocess.check_output(align_cmd).decode()
#                 if results_dir is not None:
#                     align_output_path = results_dir / "word_align.txt"
#                     align_output_path.write_text(align_output)
#                     _LOGGER.debug("Wrote %s", align_output_path)

#                 # Convert to JSON
#                 with io.StringIO(align_output) as align_file:
#                     align_results = align2json(align_file)

#     else:
#         _LOGGER.warn("word_align.pl not found in PATH. Not computing WER.")

#     # Merge WER results
#     for key, wer in align_results.items():
#         actual[key]["word_error"] = wer
#         num_words += wer["words"]
#         correct_words += wer["correct"]

#     average_transcription_speedup = 0
#     if len(speedups) > 0:
#         average_transcription_speedup = sum(speedups) / len(speedups)

#     # Summarize results
#     summary = {
#         "statistics": {
#             "num_wavs": num_wavs,
#             "num_words": num_words,
#             "num_entities": num_entities,
#             "correct_transcriptions": correct_transcriptions,
#             "correct_intent_names": correct_intent_names,
#             "correct_words": correct_words,
#             "correct_entities": correct_entities,
#             "transcription_accuracy": correct_words / num_words if num_words > 0 else 1,
#             "intent_accuracy": correct_intent_names / num_intents
#             if num_intents > 0
#             else 1,
#             "entity_accuracy": correct_entities / num_entities
#             if num_entities > 0
#             else 1,
#             "intent_entity_accuracy": correct_intent_and_entities / num_intents
#             if num_intents > 0
#             else 1,
#             "average_transcription_speedup": average_transcription_speedup,
#         },
#         "actual": actual,
#         "expected": expected,
#     }

#     print_json(summary)


# # -----------------------------------------------------------------------------


# def tune_examples(
#     args: argparse.Namespace, profile_dir: Path, profile: Dict[str, Any]
# ) -> None:
#     from voice2json import get_tuner

#     examples_dir = Path(args.directory) if args.directory is not None else Path.cwd()
#     _LOGGER.debug("Looking for examples in %s", examples_dir)

#     start_time = time.time()

#     tuner = get_tuner(profile_dir, profile)
#     tuner.tune(examples_dir)

#     end_time = time.time()
#     print("Tuning completed in", end_time - start_time, "second(s)")


# # -----------------------------------------------------------------------------


# def show_documentation(
#     args: argparse.Namespace, profile_dir: Path, profile: Dict[str, Any]
# ) -> None:
#     import http.server
#     import socketserver

#     voice2json_dir = Path(os.environ.get("voice2json_dir", os.getcwd()))
#     site_dir = voice2json_dir / "site"

#     os.chdir(site_dir)
#     Handler = http.server.SimpleHTTPRequestHandler
#     httpd = socketserver.TCPServer(("", args.port), Handler)
#     print(f"Running HTTP server at http://127.0.0.1:{args.port}")
#     httpd.serve_forever()


# # -----------------------------------------------------------------------------
# # Utilities
# # -----------------------------------------------------------------------------


def print_json(value: Any) -> None:
    """Print a single line of JSON to stdout."""
    with jsonlines.Writer(sys.stdout) as out:
        out.write(value)

    sys.stdout.flush()


def env_constructor(loader, node):
    """Expand !env STRING to replace environment variables in STRING."""
    return os.path.expandvars(node.value)


def check_trained(core: Voice2JsonCore) -> None:
    """Check important files to see if profile is not trained. Exits if it isn't."""
    # Load settings
    dictionary_path = core.ppath("speech-to-text.dictionary", "dictionary.txt")

    language_model_path = core.ppath(
        "speech-to-text.language-model", "language_model.txt"
    )

    intent_fst_path = core.ppath("intent-recognition.intent-fst", "intent.fst")

    missing = False
    for path in [dictionary_path, language_model_path, intent_fst_path]:
        if not path.exists():
            _LOGGER.fatal("Missing %s. Did you forget to run train-profile?", path)
            missing = True

    if missing:
        # Automatically exit
        sys.exit(1)


# # -----------------------------------------------------------------------------


# def speak(args: argparse.Namespace, profile_dir: Path, profile: Dict[str, Any]) -> None:
#     marytts_voice = pydash.get(profile, "text-to-speech.marytts.voice")
#     if args.espeak or (marytts_voice is None):
#         speak_espeak(args, profile_dir, profile)
#     else:
#         speak_marytts(args, profile_dir, profile, marytts_voice)


# def speak_espeak(
#     args: argparse.Namespace, profile_dir: Path, profile: Dict[str, Any]
# ) -> None:
#     voice = pydash.get(profile, "text-to-speech.espeak.voice")
#     espeak_cmd_format = pydash.get(profile, "text-to-speech.espeak.speak-command")
#     play_command = shlex.split(pydash.get(profile, "audio.play-command"))

#     # Process sentence(s)
#     if len(args.sentence) > 0:
#         sentences = args.sentence
#     else:
#         sentences = sys.stdin

#     for sentence in sentences:
#         sentence = sentence.strip()
#         espeak_cmd = shlex.split(espeak_cmd_format.format(sentence=sentence))
#         espeak_cmd.append("--stdout")

#         if voice is not None:
#             espeak_cmd.extend(["-v", str(voice)])

#         _LOGGER.debug(espeak_cmd)
#         wav_data = subprocess.check_output(espeak_cmd)

#         if args.wav_sink is not None:
#             # Write WAV output somewhere
#             if args.wav_sink == "-":
#                 # STDOUT
#                 wav_sink = sys.stdout.buffer
#             else:
#                 # File output
#                 wav_sink = open(args.wav_sink, "wb")

#             wav_sink.write(wav_data)
#             wav_sink.flush()
#         else:
#             _LOGGER.debug(play_command)

#             # Speak sentence
#             print(sentence)
#             subprocess.run(play_command, input=wav_data, check=True)


# def start_marytts(
#     args: argparse.Namespace,
#     profile_dir: Path,
#     profile: Dict[str, Any],
#     marytts_voice: str,
# ):
#     max_retries = int(pydash.get(profile, "text-to-speech.marytts.max-retries", 15))
#     retry_seconds = float(
#         pydash.get(profile, "text-to-speech.marytts.retry-seconds", 0.5)
#     )
#     marytts_locale = pydash.get(
#         profile, "text-to-speech.marytts.locale", pydash.get(profile, "language.code")
#     )
#     server_command = shlex.split(
#         pydash.get(profile, "text-to-speech.marytts.server-command")
#     )

#     _LOGGER.debug(server_command)

#     # Re-direct stderr output
#     kwargs = {}
#     if not args.debug:
#         kwargs["stderr"] = subprocess.DEVNULL

#     marytts_proc = subprocess.Popen(server_command, universal_newlines=True, **kwargs)

#     url = str(
#         pydash.get(
#             profile,
#             "text-to-speech.marytts.process-url",
#             "http://localhost:59125/process",
#         )
#     )

#     try:
#         # Check connection
#         connected = False
#         for i in range(max_retries):
#             try:
#                 requests.get(url)
#                 connected = True
#                 break
#             except Exception:
#                 time.sleep(retry_seconds)

#         if not connected:
#             _LOGGER.fatal(f"Failed to connect to MaryTTS server at {url}")
#             sys.exit(1)

#         # Set up default params
#         params = {
#             "INPUT_TEXT": "",
#             "INPUT_TYPE": "TEXT",
#             "AUDIO": "WAVE",
#             "OUTPUT_TYPE": "AUDIO",
#             "VOICE": marytts_voice,
#         }

#         if marytts_locale is not None:
#             params["LOCALE"] = marytts_locale

#     except Exception:
#         _LOGGER.exception("start_marytts")

#         # Stop MaryTTS server
#         marytts_proc.terminate()
#         marytts_proc.wait()

#         sys.exit(1)

#     return marytts_proc, url, params


# def speak_marytts(
#     args: argparse.Namespace,
#     profile_dir: Path,
#     profile: Dict[str, Any],
#     marytts_voice: str,
# ) -> None:
#     play_command = shlex.split(pydash.get(profile, "audio.play-command"))

#     marytts_proc, url, params = start_marytts(args, profile_dir, profile, marytts_voice)

#     try:
#         # Process sentence(s)
#         if len(args.sentence) > 0:
#             sentences = args.sentence
#         else:
#             sentences = sys.stdin

#         for sentence in sentences:
#             sentence = sentence.strip()
#             params["INPUT_TEXT"] = sentence
#             _LOGGER.debug(params)

#             # Do GET requests
#             result = requests.get(url, params=params)
#             if result.ok:
#                 if args.wav_sink is not None:
#                     # Write WAV output somewhere
#                     if args.wav_sink == "-":
#                         # STDOUT
#                         wav_sink = sys.stdout.buffer
#                     else:
#                         # File output
#                         wav_sink = open(args.wav_sink, "wb")

#                     wav_sink.write(result.content)
#                     wav_sink.flush()
#                 else:
#                     _LOGGER.debug(play_command)

#                     # Speak sentence
#                     print(sentence)
#                     subprocess.run(play_command, input=result.content, check=True)
#     finally:
#         # Stop MaryTTS server
#         marytts_proc.terminate()
#         marytts_proc.wait()


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
