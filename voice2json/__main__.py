"""
Command-line interface to voice2json.

For more details, see https://voice2json.org
"""

import argparse
import asyncio
import json
import logging
import os
import platform
import sys
import time
import typing
from collections import defaultdict
from pathlib import Path

import pydash
import yaml

from .core import Voice2JsonCore
from .generate import generate
from .pronounce import pronounce
from .recognize import recognize
from .record import record_command, record_examples
from .speak import speak
from .test import test_examples
from .transcribe import transcribe
from .utils import env_constructor, recursive_update, print_json
from .wake import wake

_LOGGER = logging.getLogger("voice2json")


# -----------------------------------------------------------------------------


async def main():
    """Called at startup."""
    # Expand environment variables in string value
    yaml.SafeLoader.add_constructor("!env", env_constructor)

    if len(sys.argv) > 1:
        if sys.argv[1] == "--version":
            # Patch argv to use print-version command
            sys.argv = [sys.argv[0], "print-version"]

    # Parse command-line arguments
    args = get_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    _LOGGER.debug(args)

    if args.command in ["print-downloads"]:
        # Special-case commands
        args.func(args)
    else:
        # Load profile and create core
        core = get_core(args)

        # Call sub-commmand
        try:
            await args.func(args, core)
        finally:
            await core.stop()


# -----------------------------------------------------------------------------


def get_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(prog="voice2json", description="voice2json")
    parser.add_argument("--profile", "-p", help="Path to profle directory")
    parser.add_argument("--certfile", help="Path to SSL certificate file")
    parser.add_argument("--keyfile", help="Path to SSL key file")
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

    # Create subparsers for each sub-command
    sub_parsers = parser.add_subparsers()
    sub_parsers.required = True
    sub_parsers.dest = "command"

    # -------------
    # print-version
    # -------------
    version_parser = sub_parsers.add_parser(
        "print-version", help="Print voice2json version"
    )
    version_parser.set_defaults(func=print_version)

    # -------------
    # print-profile
    # -------------
    print_parser = sub_parsers.add_parser(
        "print-profile", help="Print profile JSON to stdout"
    )
    print_parser.set_defaults(func=print_profile)

    # -------------
    # print-downloads
    # -------------
    downloads_parser = sub_parsers.add_parser(
        "print-downloads", help="Print links to download files for profile(s)"
    )
    downloads_parser.add_argument(
        "--url-format",
        default="https://github.com/synesthesiam/{profile}/raw/master/{file}",
        help="Format string for URL (receives {profile} and {file})",
    )
    downloads_parser.add_argument(
        "--no-grapheme-to-phoneme",
        action="store_true",
        help="Hide files for guessing word pronunciations",
    )
    downloads_parser.add_argument(
        "--no-open-transcription",
        action="store_true",
        help="Hide files for open transcription (pre-built)",
    )
    downloads_parser.add_argument(
        "--no-mixed-language-model",
        action="store_true",
        help="Hide files for mixed language modeling (pre-built + custom)",
    )
    downloads_parser.add_argument(
        "--no-text-to-speech", action="store_true", help="Hide files for text to speech"
    )
    downloads_parser.add_argument(
        "profile", nargs="*", default=[], help="Profile prefixes"
    )
    downloads_parser.set_defaults(func=print_downloads)

    # -------------
    # train-profile
    # -------------
    train_parser = sub_parsers.add_parser(
        "train-profile", help="Train voice2json profile"
    )
    train_parser.set_defaults(func=train)

    # --------------
    # transcribe-wav
    # --------------
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

    # ----------------
    # recognize-intent
    # ----------------
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
        action="append",
        help="Compute perplexity of input text relative to language model FST",
    )

    # --------------
    # record-command
    # --------------
    command_parser = sub_parsers.add_parser(
        "record-command", help="Record voice command and write WAV to stdout"
    )
    command_parser.add_argument(
        "--audio-source",
        "-a",
        help="File to read raw 16-bit 16Khz mono audio from (use '-' for stdin)",
    )
    command_parser.add_argument(
        "--wav-sink", "-w", help="File to write WAV data to instead of stdout"
    )
    command_parser.add_argument(
        "--output-size",
        action="store_true",
        help="Write line with output byte count before output",
    )
    command_parser.add_argument(
        "--chunk-size",
        type=int,
        default=1024,
        help="Number of bytes to read at a time from audio source",
    )
    command_parser.set_defaults(func=record_command)

    # ---------
    # wait-wake
    # ---------
    wake_parser = sub_parsers.add_parser(
        "wait-wake", help="Listen to audio until wake word is spoken"
    )
    wake_parser.add_argument(
        "--audio-source", "-a", help="File to read raw 16-bit 16Khz mono audio from"
    )
    wake_parser.add_argument(
        "--chunk-size",
        type=int,
        default=1024,
        help="Number of bytes to read at a time from audio source",
    )
    wake_parser.add_argument(
        "--exit-count",
        "-c",
        type=int,
        help="Exit after the wake word has been spoken some number of times",
    )
    wake_parser.add_argument(
        "--exit-timeout",
        type=float,
        default=0,
        help="Seconds to wait for predictions before exiting",
    )
    wake_parser.set_defaults(func=wake)

    # --------------
    # pronounce-word
    # --------------
    pronounce_parser = sub_parsers.add_parser(
        "pronounce-word", help="Speak a word phonetically"
    )
    pronounce_parser.add_argument("word", nargs="*", help="Word(s) to prononunce")
    pronounce_parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Don't speak word; only print phonemes",
    )
    pronounce_parser.add_argument(
        "--delay", "-d", type=float, default=0, help="Seconds to wait between words"
    )
    pronounce_parser.add_argument(
        "--nbest",
        "-n",
        type=int,
        default=5,
        help="Number of pronunciations to generate for unknown words",
    )
    pronounce_parser.add_argument(
        "--espeak", action="store_true", help="Use eSpeak even if MaryTTS is available"
    )
    pronounce_parser.add_argument("--wav-sink", "-w", help="File to write WAV data to")
    pronounce_parser.add_argument(
        "--newline",
        action="store_true",
        help="Print a blank line after the end of each word's pronunciations",
    )
    pronounce_parser.set_defaults(func=pronounce)

    # -----------------
    # generate-examples
    # -----------------
    generate_parser = sub_parsers.add_parser(
        "generate-examples", help="Randomly generate example intents from profile"
    )
    generate_parser.add_argument(
        "--number", "-n", type=int, required=True, help="Number of examples to generate"
    )
    generate_parser.add_argument(
        "--raw-symbols",
        action="store_true",
        help="Output symbols directly from finite state transducer",
    )
    generate_parser.add_argument(
        "--iob", action="store_true", help="Output IOB format instead of JSON"
    )
    generate_parser.set_defaults(func=generate)

    # record-examples
    record_examples_parser = sub_parsers.add_parser(
        "record-examples",
        help="Randomly generate example prompts and have the user record them",
    )
    record_examples_parser.add_argument(
        "--directory",
        "-d",
        help="Directory to save recorded WAV files and transcriptions",
    )
    record_examples_parser.add_argument(
        "--audio-source", "-a", help="File to read raw 16-bit 16Khz mono audio from"
    )
    record_examples_parser.add_argument(
        "--chunk-size",
        type=int,
        default=1024,
        help="Number of bytes to read at a time from stdin",
    )
    record_examples_parser.set_defaults(func=record_examples)

    # -------------
    # test-examples
    # -------------
    test_examples_parser = sub_parsers.add_parser(
        "test-examples", help="Test performance on previously recorded examples"
    )
    test_examples_parser.add_argument(
        "--directory", "-d", help="Directory with recorded examples"
    )
    test_examples_parser.add_argument(
        "--results", "-r", help="Directory to save test results"
    )
    test_examples_parser.add_argument(
        "--expected", help="Path to jsonl file with expected test results"
    )
    test_examples_parser.add_argument(
        "--actual", help="Path to jsonl file with actual test results"
    )
    test_examples_parser.add_argument(
        "--open",
        "-o",
        action="store_true",
        help="Use large pre-built model for transcription",
    )
    test_examples_parser.add_argument(
        "--threads",
        type=int,
        default=1,
        help="Maximum number of threads to use (default=1)",
    )
    test_examples_parser.set_defaults(func=test_examples)

    # ------------------
    # show-documentation
    # ------------------
    show_documentation_parser = sub_parsers.add_parser(
        "show-documentation", help="Run local HTTP server with documentation"
    )
    show_documentation_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to host web server on (default: 8000)",
    )
    show_documentation_parser.set_defaults(func=show_documentation)

    # speak-sentence
    speak_parser = sub_parsers.add_parser(
        "speak-sentence", help="Speak a sentence using MaryTTS"
    )
    speak_parser.add_argument("sentence", nargs="*", help="Sentence(s) to speak")
    speak_parser.add_argument("--wav-sink", "-w", help="File to write WAV data to")
    speak_parser.add_argument(
        "--espeak", action="store_true", help="Use eSpeak even if MaryTTS is available"
    )
    speak_parser.set_defaults(func=speak)

    return parser.parse_args()


# -----------------------------------------------------------------------------


def get_core(args: argparse.Namespace) -> Voice2JsonCore:
    """Load profile and create voice2json core."""
    # Load profile (YAML)
    profile_yaml: typing.Optional[Path] = None

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
    return Voice2JsonCore(
        profile_yaml, profile, certfile=args.certfile, keyfile=args.keyfile
    )


# -----------------------------------------------------------------------------


async def print_version(args: argparse.Namespace, core: Voice2JsonCore) -> None:
    """Print version."""
    version_path = Path(os.environ.get("voice2json_dir", os.getcwd())) / "VERSION"
    print(version_path.read_text().strip())


# -----------------------------------------------------------------------------


async def print_profile(args: argparse.Namespace, core: Voice2JsonCore) -> None:
    """Print all settings as JSON."""
    json.dump(core.profile, sys.stdout, indent=4)


# -----------------------------------------------------------------------------


def print_downloads(args: argparse.Namespace):
    """Print links to files for profiles."""
    downloads_dict = defaultdict(dict)
    profiles_dir = Path("etc/profiles")

    # Each YAML file is a profile name with required and optional files
    for yaml_path in profiles_dir.glob("*.yml"):
        profile_name = yaml_path.stem
        if args.profile:
            # Check prefix
            has_prefix = False
            for prefix in args.profile:
                if profile_name.startswith(prefix):
                    has_prefix = True
                    break

            if not has_prefix:
                # Skip file
                continue

        # Load YAML
        with open(yaml_path, "r") as yaml_file:
            files_yaml = yaml.safe_load(yaml_file)

        # Add files to downloads
        for condition, files in files_yaml.items():
            # Filter based on condition and arguments
            if (
                (args.no_grapheme_to_phoneme and condition == "grapheme-to-phoneme")
                or (args.no_open_transcription and condition == "open-transcription")
                or (
                    args.no_mixed_language_model and condition == "mixed-language-model"
                )
                or (args.no_text_to_speech and condition == "text-to-speech")
            ):
                continue

            for file_path, file_info in files.items():
                # Add URL to file info
                file_info["url"] = args.url_format.format(
                    profile=profile_name, file=file_path
                )
                downloads_dict[profile_name][file_path] = file_info

    print_json(downloads_dict)


# -----------------------------------------------------------------------------


async def train(args: argparse.Namespace, core: Voice2JsonCore) -> None:
    """Create speech/intent artifacts for a profile."""
    start_time = time.perf_counter()
    await core.train_profile()
    end_time = time.perf_counter()

    print("Training completed in", end_time - start_time, "second(s)")


# -----------------------------------------------------------------------------


async def show_documentation(args: argparse.Namespace, core: Voice2JsonCore) -> None:
    """Run basic web server with documentation."""
    import http.server
    import socketserver

    voice2json_dir = Path(os.environ.get("voice2json_dir", os.getcwd()))
    site_dir = voice2json_dir / "site"

    os.chdir(site_dir)
    Handler = http.server.SimpleHTTPRequestHandler
    httpd = socketserver.TCPServer(("", args.port), Handler)
    print(f"Running HTTP server at http://127.0.0.1:{args.port}")

    httpd.serve_forever()


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
