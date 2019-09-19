import sys
import os
import json
import argparse
import logging
from pathlib import Path
from typing import Set, Dict, Optional

logger = logging.getLogger("voice2json")

import yaml
import pydash
import jsonlines

from voice2json.utils import ppath

# -----------------------------------------------------------------------------


def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="voice2json")
    parser.add_argument("--profile", "-p", help="Path to profle directory")
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG log to console"
    )

    sub_parsers = parser.add_subparsers()
    sub_parsers.required = True
    sub_parsers.dest = "command"

    # train
    train_parser = sub_parsers.add_parser(
        "train-profile", help="Train voice2json profile"
    )
    train_parser.set_defaults(func=train)

    # transcribe
    transcribe_parser = sub_parsers.add_parser(
        "transcribe-wav", help="Transcribe WAV file to text"
    )
    transcribe_parser.set_defaults(func=transcribe)
    transcribe_parser.add_argument(
        "wav_file", nargs="*", default=[], help="Path(s) to WAV file(s)"
    )

    # recognized
    recognize_parser = sub_parsers.add_parser(
        "recognize-text", help="Recognize JSON intent from text"
    )
    recognize_parser.set_defaults(func=recognize)
    recognize_parser.add_argument(
        "sentence", nargs="*", default=[], help="Sentences to recognize"
    )
    recognize_parser.add_argument(
        "--text-input", action="store_true", help="Input is plain text instead of JSON"
    )

    # record-command
    command_parser = sub_parsers.add_parser(
        "record-command",
        help="Record voice command from stdin audio, write WAV to stdout",
    )
    command_parser.set_defaults(func=record_command)

    # -------------------------------------------------------------------------

    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)

    logger.debug(args)

    if args.profile is None:
        # Guess profile location in $HOME/.config/voice2json
        if "XDG_CONFIG_HOME" in os.environ:
            config_home = Path(os.environ["XDG_CONFIG_HOME"])
        else:
            config_home = Path("~/.config").expanduser()

        profile_dir = config_home / "voice2json"
        logger.debug(f"Assuming profile is at {profile_dir}")

    else:
        # Use profile provided on command line
        profile_dir = Path(args.profile)

    # Set environment variable usually referenced in profile
    os.environ["profile_dir"] = str(profile_dir)

    # Load profile
    profile_yaml = profile_dir / "profile.yml"
    logger.debug(f"Loading profile from {profile_yaml}")

    with open(profile_yaml, "r") as profile_file:
        profile = yaml.safe_load(profile_file)

    # Call sub-commmand
    args.func(args, profile_dir, profile)


# -----------------------------------------------------------------------------


def train(args: argparse.Namespace, profile_dir: Path, profile) -> None:
    from voice2json.train import train_profile

    # Strip voice2json command-line arguments so doit won't pick them up
    sys.argv = [sys.argv[0]]

    train_profile(profile_dir, profile)


# -----------------------------------------------------------------------------


def transcribe(args: argparse.Namespace, profile_dir: Path, profile) -> None:
    from voice2json.speech.pocketsphinx import get_decoder, transcribe
    from voice2json.utils import maybe_convert_wav

    # Load settings
    acoustic_model = ppath(
        profile, profile_dir, "speech-to-text.acoustic-model", "acoustic_model"
    )
    dictionary = ppath(
        profile, profile_dir, "speech-to-text.dictionary", "dictionary.txt"
    )
    language_model = ppath(
        profile, profile_dir, "speech-to-text.language-model", "language_model.txt"
    )
    mllr_matrix = ppath(profile, profile_dir, "speech-to-text.mllr-matrix")

    # Load deocder
    decoder = get_decoder(
        acoustic_model, dictionary, language_model, mllr_matrix, debug=args.debug
    )

    if len(args.wav_file) > 0:
        pass
    else:
        # Read WAV data from stdin
        logger.debug("Reading WAV data from stdin")
        wav_data = sys.stdin.buffer.read()
        audio_data = maybe_convert_wav(wav_data)
        result = transcribe(decoder, audio_data)
        print_json(result)


# -----------------------------------------------------------------------------


def recognize(args: argparse.Namespace, profile_dir: Path, profile) -> None:
    import pywrapfst as fst
    import networkx as nx
    from voice2json.intent.fsticuffs import (
        recognize,
        recognize_fuzzy,
        empty_intent,
        fst_to_graph,
    )

    # Load settings
    intent_fst_path = ppath(
        profile, profile_dir, "intent-recognition.intent-fst", "intent.fst"
    )
    stop_words_path = ppath(profile, profile_dir, "intent-recognition.stop-words")
    lower_case = pydash.get(profile, "intent-recognition.lower-case", False)
    fuzzy = pydash.get(profile, "intent-recognition.fuzzy", True)
    skip_unknown = pydash.get(profile, "intent-recognition.skip_unknown", True)

    # Load intent finite state transducer
    intent_fst = fst.Fst.read(str(intent_fst_path))

    # Load stop words (common words that can be safely ignored)
    stop_words: Set[str] = set()
    if stop_words_path is not None:
        stop_words.extend(w.strip() for w in stop_words_path.read_text().splitlines())

    # Ignore words outside of input symbol table
    known_tokens: Set[str] = set()
    if skip_unknown:
        in_symbols = intent_fst.input_symbols()
        for i in range(in_symbols.num_symbols()):
            key = in_symbols.get_nth_key(i)
            token = in_symbols.find(i).decode()

            # Exclude meta tokens and <eps>
            if not (token.startswith("__") or token.startswith("<")):
                known_tokens.add(token)

    intent_graph: Optional[nx.DiGraph] = None
    if fuzzy:
        # Convert to graph for fuzzy searching
        intent_graph = fst_to_graph(intent_fst)

    # -------------------------------------------------------------------------

    if len(args.sentence) > 0:
        sentences = args.sentence
    else:
        logger.debug("Reading sentences from stdin")
        sentences = sys.stdin

    # Process sentences
    for sentence in sentences:
        if args.text_input:
            # Input is plain text
            text = sentence
            sentence_object = {"text": text}
        else:
            # Input is JSON
            sentence_object = json.loads(sentence)
            text = sentence_object.get("text", "")

        if lower_case:
            text = text.lower()

        if fuzzy:
            # Fuzzy matching
            intent = recognize_fuzzy(
                intent_graph, text, known_tokens=known_tokens, stop_words=stop_words
            )
        else:
            # Strict matching
            intent = recognize(intent_fst, text, known_tokens)

        # Merge with input object
        for key, value in intent.items():
            sentence_object[key] = value

        print_json(sentence_object)


# -----------------------------------------------------------------------------


def record_command(args: argparse.Namespace, profile_dir: Path, profile) -> None:
    from voice2json.command.webrtcvad import wait_for_command
    from voice2json.utils import buffer_to_wav

    logger.debug("Recording raw 16-bit 16Khz mono audio from stdin")

    audio_buffer = wait_for_command(sys.stdin.buffer)
    wav_bytes = buffer_to_wav(audio_buffer)
    sys.stdout.buffer.write(wav_bytes)


# -----------------------------------------------------------------------------
# Utilities
# -----------------------------------------------------------------------------


def print_json(value) -> None:
    """Prints a single line of JSON to stdout."""
    with jsonlines.Writer(sys.stdout) as out:
        out.write(value)


def env_constructor(loader, node):
    """Expands !env STRING to replace environment variables in STRING."""
    return os.path.expandvars(node.value)


yaml.SafeLoader.add_constructor("!env", env_constructor)

# -----------------------------------------------------------------------------


if __name__ == "__main__":
    main()
