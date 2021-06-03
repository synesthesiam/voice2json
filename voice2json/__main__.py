"""
Command-line interface to voice2json.

For more details, see https://voice2json.org
"""

import argparse
import asyncio
import collections
import json
import logging
import os
import platform
import ssl
import sys
import time
import typing
from pathlib import Path

import pydash
import yaml
from tqdm import tqdm

from .core import Voice2JsonCore
from .generate import generate
from .pronounce import pronounce
from .recognize import recognize
from .record import record_command, record_examples
from .speak import speak
from .test import test_examples
from .transcribe import transcribe_stream, transcribe_wav
from .utils import (
    download_file,
    env_constructor,
    get_profile_downloads,
    print_json,
    reassemble_large_files,
    recursive_update,
)
from .wake import wake

_LOGGER = logging.getLogger("voice2json")

DEFAULT_PROFILE = "en-us_kaldi-zamia"

# -----------------------------------------------------------------------------


async def main():
    """Called at startup."""
    # Expand environment variables in string value
    yaml.SafeLoader.add_constructor("!env", env_constructor)

    if len(sys.argv) > 1:
        if sys.argv[1] == "--version":
            # Patch argv to use print-version command
            sys.argv = [sys.argv[0], "print-version"]
    else:
        # Patch argv to use print-profiles command
        sys.argv = [sys.argv[0], "print-downloads", "--list-profiles"]

    # Parse command-line arguments
    args = get_args()

    # voice2json_dir
    if not args.base_directory:
        args.base_directory = os.environ.get("voice2json_dir", os.getcwd())

    args.base_directory = Path(args.base_directory)

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    _LOGGER.debug(args)

    if args.command in ["print-downloads", "print-version", "download-profile"]:
        # Special-case commands (no core loaded)
        await args.func(args)
    else:
        # Load profile and create core
        core = await get_core(args)

        # Call sub-commmand
        try:
            await args.func(args, core)
        finally:
            await core.stop()


# -----------------------------------------------------------------------------


def get_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(prog="voice2json", description="voice2json")

    def add_default_arguments(argparser):
        argparser.add_argument("--profile", "-p", help="Path to profile directory")
        argparser.add_argument(
            "--base-directory",
            help="Directory with shared voice2json files (voice2json_dir)",
        )
        argparser.add_argument("--certfile", help="Path to SSL certificate file")
        argparser.add_argument("--keyfile", help="Path to SSL key file")
        argparser.add_argument(
            "--setting",
            "-s",
            nargs=2,
            action="append",
            default=[],
            help="Override profile setting(s)",
        )
        argparser.add_argument(
            "--machine",
            default=platform.machine(),
            help="Platform machine to use (default: host)",
        )

        argparser.add_argument(
            "--no-auto-download",
            action="store_true",
            help="Don't automatically download profile files",
        )

        argparser.add_argument(
            "--no-auto-train",
            action="store_true",
            help="Don't automatically train profile",
        )

        argparser.add_argument(
            "--debug", action="store_true", help="Print DEBUG messages to console"
        )

    add_default_arguments(parser)

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

    # ---------------
    # print-downloads
    # ---------------
    downloads_parser = sub_parsers.add_parser(
        "print-downloads", help="Print links to download files for profile(s)"
    )
    downloads_parser.add_argument(
        "--url-format",
        default="https://raw.githubusercontent.com/synesthesiam/{profile}/master/{file}",
        help="Format string for URL (receives {profile}, {file}, and {machine})",
    )
    downloads_parser.add_argument(
        "--only-missing",
        action="store_true",
        help="Only print files that don't exist in your profile directory",
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
        "--with-examples", action="store_true", help="Include example sentences, etc."
    )
    downloads_parser.add_argument(
        "profile_names", nargs="*", help="Profile names to check"
    )
    downloads_parser.add_argument(
        "--list-profiles", action="store_true", help="List names of known profiles"
    )
    downloads_parser.set_defaults(func=print_downloads)

    # -------------
    # print-files
    # -------------
    print_files_parser = sub_parsers.add_parser(
        "print-files", help="Print paths to profile files for backup"
    )
    print_files_parser.set_defaults(func=print_files)

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
    transcribe_wav_parser = sub_parsers.add_parser(
        "transcribe-wav", help="Transcribe WAV file to text"
    )
    transcribe_wav_parser.set_defaults(func=transcribe_wav)
    transcribe_wav_parser.add_argument(
        "--stdin-files",
        "-f",
        action="store_true",
        help="Read WAV file paths from stdin instead of WAV data",
    )
    transcribe_wav_parser.add_argument(
        "--open",
        "-o",
        action="store_true",
        help="Use large pre-built model for transcription",
    )
    transcribe_wav_parser.add_argument(
        "--relative-directory", help="Set wav_name as path relative to this directory"
    )
    transcribe_wav_parser.add_argument(
        "--input-size",
        action="store_true",
        help="WAV file byte size is sent on a separate line for each input WAV on stdin",
    )
    transcribe_wav_parser.add_argument(
        "wav_file", nargs="*", default=[], help="Path(s) to WAV file(s)"
    )

    # -----------------
    # transcribe-stream
    # -----------------
    transcribe_stream_parser = sub_parsers.add_parser(
        "transcribe-stream", help="Transcribe live stream of WAV chunks to text"
    )
    transcribe_stream_parser.set_defaults(func=transcribe_stream)
    transcribe_stream_parser.add_argument(
        "--audio-source",
        "-a",
        help="File to read raw 16-bit 16Khz mono audio from (use '-' for stdin)",
    )
    transcribe_stream_parser.add_argument(
        "--open",
        "-o",
        action="store_true",
        help="Use large pre-built model for transcription",
    )
    transcribe_stream_parser.add_argument(
        "--exit-count",
        "-c",
        type=int,
        help="Exit after some number of voice commands have been recorded/transcribed",
    )
    transcribe_stream_parser.add_argument(
        "--chunk-size",
        type=int,
        default=1024,
        help="Number of bytes to read at a time from audio source",
    )
    transcribe_stream_parser.add_argument(
        "--wav-sink", help="File or directory to write voice commands to"
    )
    transcribe_stream_parser.add_argument(
        "--wav-filename",
        default="%Y%m%d-%H%M%S",
        help="strftime format of WAV file name in directory",
    )
    transcribe_stream_parser.add_argument(
        "--event-sink", "-e", help="File to write JSON voice command events to"
    )
    transcribe_stream_parser.add_argument(
        "--timeout",
        type=float,
        help="Seconds to wait for a transcription before exiting (default: None)",
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
    recognize_parser.add_argument(
        "--intent-filter",
        "-f",
        nargs="+",
        help="Intent names that allowed to be recognized",
    )
    recognize_parser.add_argument(
        "--transcription-property",
        default="text",
        help="JSON property containing transcription text (default: text)",
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
    command_parser.add_argument(
        "--event-sink", "-e", help="File to write JSON events to instead of stdout"
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
    wake_parser.add_argument("--model", help="Override model in profile")
    wake_parser.add_argument(
        "--chunk-size",
        type=int,
        default=2048,
        help="Number of bytes to read at a time from audio source",
    )
    wake_parser.add_argument(
        "--exit-count",
        "-c",
        type=int,
        help="Exit after the wake word has been spoken some number of times",
    )
    wake_parser.set_defaults(func=wake)

    # --------------
    # pronounce-word
    # --------------
    pronounce_parser = sub_parsers.add_parser(
        "pronounce-word", help="Speak a word phonetically"
    )
    pronounce_parser.add_argument("word", nargs="*", help="Word(s) to pronounce")
    pronounce_parser.add_argument(
        "--sounds-like",
        action="store_true",
        help="Interpret pronunciation(s) like sounds_like.txt",
    )
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
        "--marytts", action="store_true", help="Use MaryTTS instead of eSpeak"
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

    # --------------
    # speak-sentence
    # --------------
    speak_parser = sub_parsers.add_parser(
        "speak-sentence", help="Speak a sentence using MaryTTS"
    )
    speak_parser.add_argument("sentence", nargs="*", help="Sentence(s) to speak")
    speak_parser.add_argument("--wav-sink", "-w", help="File to write WAV data to")
    speak_parser.add_argument(
        "--marytts", action="store_true", help="Use MaryTTS instead of eSpeak"
    )
    speak_parser.set_defaults(func=speak)

    # ----------------
    # download-profile
    # ----------------
    download_profile_parser = sub_parsers.add_parser(
        "download-profile", help="Download and verify profile files"
    )
    download_profile_parser.add_argument(
        "conditions",
        nargs="*",
        help="Conditions to download files for, such as open-transcription (default: all conditions)",
    )
    download_profile_parser.add_argument(
        "--url-format",
        help="Override format string for URL (receives {profile}, {file}, and {machine})",
    )
    download_profile_parser.set_defaults(func=download_profile)

    return parser.parse_args()


# -----------------------------------------------------------------------------


def get_profile_location(
    args: argparse.Namespace,
) -> typing.Tuple[Path, Path, typing.Optional[str]]:
    """Return detected profile directory and YAML file path."""
    profile_yaml: typing.Optional[Path] = None
    profile_dir: typing.Optional[Path] = None
    profile_name: typing.Optional[str] = None

    if args.profile is None:
        # Guess profile location in $HOME/.config/voice2json
        if "XDG_CONFIG_HOME" in os.environ:
            config_home = Path(os.environ["XDG_CONFIG_HOME"])
        else:
            config_home = Path("~/.config").expanduser()

        profile_dir = config_home / "voice2json"

        if profile_dir.is_dir():
            _LOGGER.debug("Using profile at %s", profile_dir)
        else:
            profile_name = DEFAULT_PROFILE
            profile_dir = None  # set automatically later
            _LOGGER.debug("Using default profile %s", profile_name)
    else:
        # Use profile provided on command line
        profile_dir_or_file = Path(args.profile)
        if profile_dir_or_file.is_dir():
            # Assume directory with profile.yaml
            profile_dir = profile_dir_or_file
        elif profile_dir_or_file.is_file():
            # Assume YAML file
            profile_dir = profile_dir_or_file.parent
            profile_yaml = profile_dir_or_file
        else:
            # Assume name
            profile_name = PROFILE_ALIASES.get(args.profile)
            profile_dir = None  # set automatically later

    if profile_dir is not None:
        profile_dir = profile_dir.resolve()

        if profile_yaml is None:
            profile_yaml = profile_dir / "profile.yml"

    if profile_name is not None:
        if profile_dir is None:
            # Guess shared profile location in $HOME/.local/share/voice2json
            if "XDG_DATA_HOME" in os.environ:
                share_home = Path(os.environ["XDG_DATA_HOME"])
            else:
                share_home = Path("~/.local/share/voice2json").expanduser()

            profile_dir = share_home / profile_name
            profile_yaml = profile_dir / "profile.yml"

    assert profile_dir is not None
    assert profile_yaml is not None

    return profile_dir, profile_yaml, profile_name


# Profiles to use when only language/locale is given
PROFILE_ALIASES = {
    "ca": "ca-es_pocketsphinx-cmu",
    "ca-es": "ca-es_pocketsphinx-cmu",
    "cs": "cs-cz_kaldi-rhasspy",
    "cs-cz": "cs-cz_kaldi-rhasspy",
    "de": "de_kaldi-zamia",
    "de-de": "de_kaldi-zamia",
    "en": "en-us_kaldi-zamia",
    "en-us": "en-us_kaldi-zamia",
    "en-in": "en-in_pocketsphinx-cmu",
    "el": "el-gr_pocketsphinx-cmu",
    "el-gr": "el-gr_pocketsphinx-cmu",
    "es": "es_kaldi-rhasspy",
    "es-es": "es_kaldi-rhasspy",
    "es-mexican": "es-mexican_pocketsphinx-cmu",
    "fr": "fr_kaldi-guyot",
    "fr-fr": "fr_kaldi-guyot",
    "hi": "hi_pocketsphinx-cmu",
    "it": "it_deepspeech-mozillaitalia",
    "it-it": "it_deepspeech-mozillaitalia",
    "ko": "ko-kr_kaldi-montreal",
    "ko-kr": "ko-kr_kaldi-montreal",
    "kz": "kz_pocketsphinx-cmu",
    "nl": "nl_kaldi-cgn",
    "pl": "pl_deepspeech-jaco",
    "pt": "pt-br_pocketsphinx-cmu",
    "pt-br": "pt-br_pocketsphinx-cmu",
    "ru": "ru_kaldi-rhasspy",
    "ru-ru": "ru_kaldi-rhasspy",
    "sv": "sv_kaldi-rhasspy",
    "sv-se": "sv_kaldi-rhasspy",
    "vi": "vi_kaldi-montreal",
    "zh": "zh-cn_pocketsphinx-cmu",
    "zh-cn": "zh-cn_pocketsphinx-cmu",
}


def load_profile(
    profile_dir: Path, profile_yaml: Path, args: argparse.Namespace
) -> typing.Dict[str, typing.Any]:
    """Load profile YAML with default settings, overrides, and platform-specific settings"""
    # Set environment variable usually referenced in profile
    os.environ["profile_dir"] = str(profile_dir)

    # x86_64, armv7l, aarch64, ...
    os.environ["machine"] = args.machine

    # Load profile defaults
    defaults_yaml = args.base_directory / "etc" / "profile.defaults.yml"
    if defaults_yaml.exists():
        _LOGGER.debug("Loading profile defaults from %s", defaults_yaml)
        with open(defaults_yaml, "r") as defaults_file:
            profile = yaml.safe_load(defaults_file)
    else:
        # No defaults
        profile = {}

    # Load profile (YAML)
    _LOGGER.debug("Loading profile from %s", profile_yaml)

    if profile_yaml.exists():
        os.environ["profile_file"] = str(profile_yaml)

        with open(profile_yaml, "r") as profile_file:
            recursive_update(profile, yaml.safe_load(profile_file) or {})
    else:
        _LOGGER.warning("%s does not exist. Using default settings.", profile_yaml)

    # Override with platform-specific settings
    platform_overrides = profile.get("platform", [])
    for platform_settings in platform_overrides:
        machines = platform_settings.get("machine")
        machine_settings = platform_settings.get("settings", {})

        if machines and machine_settings:
            if isinstance(machines, str):
                # Ensure list
                machines = [machines]

            if args.machine in machines:
                # Machine match: override settings
                for key, value in machine_settings.items():
                    _LOGGER.debug("Overriding %s (machine=%s)", key, args.machine)
                    recursive_update(profile[key], value)

    # Override with user settings
    for setting_path, setting_value in args.setting:
        try:
            setting_value = json.loads(setting_value)
        except json.JSONDecodeError:
            _LOGGER.warning(
                "Interpreting setting for %s as a string. Surround with quotes to avoid this warning.",
                setting_path,
            )
            pass

        _LOGGER.debug("Overriding %s with %s", setting_path, setting_value)
        pydash.set_(profile, setting_path, setting_value)

    return profile


async def get_core(args: argparse.Namespace) -> Voice2JsonCore:
    """Load/download/train profile and create voice2json core."""
    profile_dir, profile_yaml, profile_name = get_profile_location(args)

    if profile_name is not None:
        # May need to download files
        download_yaml = args.base_directory / "etc" / "profiles" / f"{profile_name}.yml"
        _LOGGER.debug("Trying to load download info from %s", download_yaml)
        with open(download_yaml, "r") as download_yaml_file:
            files_dict = yaml.safe_load(download_yaml_file)

        # Create SSL context for file downloads
        ssl_context = ssl.SSLContext()
        if args.certfile:
            # User-provided SSL certificate
            ssl_context.load_cert_chain(args.certfile, args.keyfile)

        download_settings: typing.Dict[str, typing.Any] = {}
        if args.command == "pronounce-word":
            download_settings["grapheme_to_phoneme"] = True

        if args.command in {"pronounce-word", "speak-sentence"}:
            download_settings["text_to_speech"] = True

        if args.command in {"transcribe-wav", "transcribe-stream"}:
            download_settings["grapheme_to_phoneme"] = True

            # Open transcription
            if args.open:
                download_settings["open_transcription"] = True

        # Create asyncio download tasks for missing files
        download_tasks = []
        for download_info in get_profile_downloads(
            profile_name, files_dict, profile_dir, **download_settings
        ):
            url = download_info["url"]
            target_path = profile_dir / download_info["file"]
            _LOGGER.debug("%s => %s", url, target_path)

            download_tasks.append(
                asyncio.create_task(
                    download_file(url, target_path, ssl_context=ssl_context)
                )
            )

        if download_tasks:
            if args.no_auto_download:
                _LOGGER.warning(
                    "There are %s profile file(s) missing, but automatic download has been disabled.",
                    len(download_tasks),
                )
                _LOGGER.warning(
                    "Training and execution will likely fail. Run with --debug for more info."
                )
            else:
                # Download missing profile files with a progress bar
                _LOGGER.info(
                    "Downloading %s file(s) for profile %s to %s",
                    len(download_tasks),
                    profile_name,
                    profile_dir,
                )

                with tqdm(total=len(download_tasks)) as pbar:
                    for done_task in asyncio.as_completed(download_tasks):
                        await done_task
                        pbar.update(1)

    profile = load_profile(profile_dir, profile_yaml, args)

    # Create core
    core = Voice2JsonCore(
        profile_yaml, profile, certfile=args.certfile, keyfile=args.keyfile
    )

    # Reassemble any large files that were downloaded
    await reassemble_large_files(pydash.get(profile, "training.large-files", []))

    if (
        (args.command != "train-profile")
        and (not args.no_auto_train)
        and not core.check_trained()
    ):
        # Automatically train
        _LOGGER.info("Automatically training profile")
        start_time = time.perf_counter()
        await core.train_profile()
        end_time = time.perf_counter()

        _LOGGER.debug("Training completed in %s second(s)", end_time - start_time)

    return core


# -----------------------------------------------------------------------------


async def print_version(args: argparse.Namespace) -> None:
    """Print version."""
    version_path = args.base_directory / "VERSION"
    print(version_path.read_text().strip())


# -----------------------------------------------------------------------------


async def print_profile(args: argparse.Namespace, core: Voice2JsonCore) -> None:
    """Print all settings as JSON."""
    json.dump(core.profile, sys.stdout, indent=4)


# -----------------------------------------------------------------------------


async def print_files(args: argparse.Namespace, core: Voice2JsonCore) -> None:
    """Print paths to user profile files for backup."""
    backup_paths = (
        [
            core.profile_file,
            core.profile_dir / "sentences.ini",
            core.profile_dir / "custom_words.txt",
            core.profile_dir / "sounds_like.txt",
        ]
        + list((core.profile_dir / "slots").rglob("*"))
        + list((core.profile_dir / "slot_programs").rglob("*"))
        + list((core.profile_dir / "converters").rglob("*"))
    )

    for backup_path in backup_paths:
        if backup_path.is_file():
            print(backup_path.absolute())


# -----------------------------------------------------------------------------


async def print_downloads(args: argparse.Namespace) -> None:
    """Print links to files for profiles."""
    profiles_dir = args.base_directory / "etc" / "profiles"

    if args.list_profiles:
        _LOGGER.info("Listing available profiles from %s", profiles_dir)
        _LOGGER.info("Use voice2json -p <PROFILE_NAME> <COMMAND>")

        # en-us_kaldi-zamia -> en
        short_aliases = {}
        for alias, full_name in PROFILE_ALIASES.items():
            if "-" not in alias:
                short_aliases[full_name] = alias

        # List profile names and exit
        profile_descriptions = {}
        for profile_path in profiles_dir.glob("*.yml"):
            try:
                with open(profile_path, "r") as profile_file:
                    files_yaml = yaml.safe_load(profile_file)
                    description = files_yaml.get("description", "")

                profile_name = profile_path.stem
                profile_descriptions[profile_name] = description
            except Exception:
                _LOGGER.exception(profile_path)

        for profile_name, description in sorted(profile_descriptions.items()):
            print(
                profile_name, short_aliases.get(profile_name, ""), description, sep="\t"
            )

        return

    # Check profile files
    if "XDG_DATA_HOME" in os.environ:
        share_home = Path(os.environ["XDG_DATA_HOME"])
    else:
        share_home = Path("~/.local/share/voice2json").expanduser()

    # Names of profiles to check
    profile_names = set(PROFILE_ALIASES.get(name) for name in args.profile_names)

    # Each YAML file is a profile name with required and optional files
    for yaml_path in profiles_dir.glob("*.yml"):
        profile_name = yaml_path.stem
        if profile_names and (profile_name not in profile_names):
            # Skip file
            _LOGGER.debug("Skipping %s (not in %s)", yaml_path, profile_names)
            continue

        profile_dir = share_home / profile_name

        # Load YAML
        _LOGGER.debug("Loading %s", yaml_path)
        with open(yaml_path, "r") as yaml_file:
            files_yaml = yaml.safe_load(yaml_file)

        # Add files to downloads
        for condition, files in files_yaml.items():
            if not isinstance(files, collections.abc.Mapping):
                continue

            # Filter based on condition and arguments
            if (
                (args.no_grapheme_to_phoneme and condition == "grapheme-to-phoneme")
                or (args.no_open_transcription and condition == "open-transcription")
                or (
                    args.no_mixed_language_model and condition == "mixed-language-model"
                )
                or (args.no_text_to_speech and condition == "text-to-speech")
                or (not args.with_examples and condition == "examples")
            ):
                _LOGGER.debug("Excluding condition %s", condition)
                continue

            for file_path, file_info in files.items():
                _LOGGER.debug("Checking %s", file_path)

                if args.only_missing:
                    # Check if file is missing
                    real_file_name = file_info.get("file-name")
                    if real_file_name:
                        # Use combined/unzipped file name
                        expected_path = (
                            profile_dir / Path(file_path).parent / real_file_name
                        )
                    else:
                        expected_path = profile_dir / file_path

                    if expected_path.is_file():
                        # Skip existing file
                        _LOGGER.debug(
                            "Excluding %s (%s exists)", file_path, expected_path
                        )
                        continue

                    _LOGGER.debug("%s does not exist (%s)", expected_path, file_path)

                # Check machine
                platforms = file_info.get("platform")
                if platforms:
                    machine_match = False
                    for platform_matches in platforms:
                        if args.machine == platform_matches.get("machine", ""):
                            machine_match = True
                            break

                    if not machine_match:
                        _LOGGER.debug("Excluding %s (machine mismatch)", file_path)
                        continue

                # Add extra info to file info
                file_info["condition"] = condition
                file_info["file"] = file_path
                file_info["profile"] = profile_name
                file_info["url"] = args.url_format.format(
                    profile=profile_name, file=file_path, machine=args.machine
                )
                file_info["profile-directory"] = str(profile_dir)

                print_json(file_info)


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

    site_dir = args.base_directory / "site"

    os.chdir(site_dir)
    Handler = http.server.SimpleHTTPRequestHandler
    httpd = socketserver.TCPServer(("", args.port), Handler)
    print(f"Running HTTP server at http://127.0.0.1:{args.port}")

    httpd.serve_forever()


# -----------------------------------------------------------------------------


async def download_profile(args: argparse.Namespace) -> None:
    """Download profile files."""
    profile_dir, profile_yaml, profile_name = get_profile_location(args)

    if profile_name is None:
        _LOGGER.fatal("Can only download files for known profile names")
        return

    # May need to download files
    download_yaml = args.base_directory / "etc" / "profiles" / f"{profile_name}.yml"
    _LOGGER.debug("Trying to load download info from %s", download_yaml)
    with open(download_yaml, "r") as download_yaml_file:
        files_dict = yaml.safe_load(download_yaml_file)

    # Create SSL context for file downloads
    ssl_context = ssl.SSLContext()
    if args.certfile:
        # User-provided SSL certificate
        ssl_context.load_cert_chain(args.certfile, args.keyfile)

    conditions = set(args.conditions)

    download_settings: typing.Dict[str, typing.Any] = {}
    if (not conditions) or ("grapheme-to-phoneme" in conditions):
        download_settings["grapheme_to_phoneme"] = True

    if (not conditions) or ("text-to-speech" in conditions):
        download_settings["text_to_speech"] = True

    if (not conditions) or ("open-transcription" in conditions):
        download_settings["open_transcription"] = True

    # Don't automatically include mixed language model condition since its rarely used
    if "mixed-language-model" in conditions:
        download_settings["mixed_language_model"] = True

    # Create asyncio download tasks for missing files
    download_tasks = []
    for download_info in get_profile_downloads(
        profile_name, files_dict, profile_dir, **download_settings
    ):
        url = download_info["url"]
        target_path = profile_dir / download_info["file"]
        _LOGGER.debug("%s => %s", url, target_path)

        download_tasks.append(
            asyncio.create_task(
                download_file(url, target_path, ssl_context=ssl_context)
            )
        )

    if download_tasks:
        # Download missing profile files with a progress bar
        _LOGGER.info(
            "Downloading %s file(s) for profile %s to %s",
            len(download_tasks),
            profile_name,
            profile_dir,
        )

        with tqdm(total=len(download_tasks)) as pbar:
            for done_task in asyncio.as_completed(download_tasks):
                await done_task
                pbar.update(1)

    profile = load_profile(profile_dir, profile_yaml, args)

    # Reassemble any large files that were downloaded
    await reassemble_large_files(pydash.get(profile, "training.large-files", []))

    print("Downloaded", len(download_tasks), "file(s) to", str(profile_dir))


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
