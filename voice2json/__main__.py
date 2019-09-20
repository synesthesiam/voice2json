#!/usr/bin/env python3

import sys
import re
import os
import json
import time
import argparse
import logging
import tempfile
import subprocess
from pathlib import Path
from collections import defaultdict
from typing import Set, Dict, Optional, List

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

    # train-profile
    train_parser = sub_parsers.add_parser(
        "train-profile", help="Train voice2json profile"
    )
    train_parser.set_defaults(func=train)

    # transcribe-wav
    transcribe_parser = sub_parsers.add_parser(
        "transcribe-wav", help="Transcribe WAV file to text"
    )
    transcribe_parser.set_defaults(func=transcribe)
    transcribe_parser.add_argument(
        "wav_file", nargs="*", default=[], help="Path(s) to WAV file(s)"
    )

    # recognize-text
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

    # wait-wake
    wake_parser = sub_parsers.add_parser(
        "wait-wake", help="Listen to audio from stdin, wait until wake word is spoken"
    )
    wake_parser.set_defaults(func=wake)

    # pronounce-word
    pronounce_parser = sub_parsers.add_parser(
        "pronounce-word", help="Speak a word phonetically"
    )
    pronounce_parser.add_argument("word", nargs="*", help="Word(s) to prononunce")
    pronounce_parser.add_argument(
        "--quiet", action="store_true", help="Don't speak word; only print phonemes"
    )
    pronounce_parser.add_argument(
        "--delay", type=float, default=0, help="Seconds to wait between words"
    )
    pronounce_parser.set_defaults(func=pronounce)

    # generate-sentences
    generate_parser = sub_parsers.add_parser(
        "generate-sentences", help="Randomly generate sentences from profile"
    )
    generate_parser.add_argument(
        "--samples", type=int, required=True, help="Number of sentences to generate"
    )
    generate_parser.add_argument(
        "--meta", action="store_true", help="Include meta tags"
    )
    generate_parser.set_defaults(func=generate)

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


def wake(args: argparse.Namespace, profile_dir: Path, profile) -> None:
    import struct
    from voice2json.wake.porcupine import Porcupine

    # Load settings
    library_path = ppath(profile, profile_dir, "wake-word.library-file")
    params_path = ppath(profile, profile_dir, "wake-word.params-file")
    keyword_path = ppath(profile, profile_dir, "wake-word.keyword-file")
    sensitivity = float(pydash.get(profile, "wake-word.sensitivity", 0.5))

    # Load porcupine
    handle = Porcupine(
        str(library_path),
        str(params_path),
        keyword_file_paths=[str(keyword_path)],
        sensitivities=[sensitivity],
    )

    chunk_size = handle.frame_length * 2
    chunk_format = "h" * handle.frame_length

    # Process audio
    logger.debug("Recording raw 16-bit 16Khz mono audio from stdin")

    chunk = sys.stdin.buffer.read(chunk_size)
    while len(chunk) == chunk_size:
        # Process audio chunk
        chunk = struct.unpack_from(chunk_format, chunk)
        keyword_index = handle.process(chunk)

        if keyword_index:
            result = {"keyword": str(keyword_path)}
            print_json(result)

        chunk = sys.stdin.buffer.read(chunk_size)


# -----------------------------------------------------------------------------


def pronounce(args: argparse.Namespace, profile_dir: Path, profile) -> None:
    from voice2json.utils import read_dict

    base_dictionary_path = ppath(
        profile, profile_dir, "training.base_dictionary", "base_dictionary.txt"
    )
    dictionary_path = ppath(
        profile, profile_dir, "training.dictionary", "dictionary.txt"
    )
    g2p_path = ppath(profile, profile_dir, "training.g2p-model", "g2p.fst")
    g2p_exists = g2p_path.exists()

    map_path = ppath(
        profile, profile_dir, "text-to-speech.phoneme-map", "espeak_phonemes.txt"
    )
    map_exists = map_path.exists()

    # Load dictionaries
    pronunciations: Dict[str, List[str]] = defaultdict(list)

    for dict_path in [dictionary_path, base_dictionary_path]:
        if dict_path.exists():
            with open(dict_path, "r") as dict_file:
                read_dict(dict_file, pronunciations)

    if len(args.word) > 0:
        words = args.word
    else:
        words = sys.stdin

    # Process words
    for word in words:
        word = word.strip()
        dict_phonemes = None

        if word in pronunciations:
            # Use first pronunciation in dictionary
            dict_phonemes = re.split(r"\s+", pronunciations[word][0])
        elif g2p_exists:
            # Guess pronunciation with phonetisaurus
            logger.debug(f"Guessing pronunciation for {word}")

            with tempfile.NamedTemporaryFile(mode="w") as word_file:
                print(word, file=word_file)
                word_file.seek(0)

                phonetisaurus_cmd = [
                    "phonetisaurus-apply",
                    "--model",
                    str(g2p_path),
                    "--word_list",
                    word_file.name,
                    "--nbest",
                    "1",
                ]

                logger.debug(phonetisaurus_cmd)
                output_lines = (
                    subprocess.check_output(phonetisaurus_cmd).decode().splitlines()
                )
                dict_phonemes = re.split(r"\s+", output_lines[0].strip())[1:]
        else:
            logger.warn(f"No pronunciation for {word}")

        if dict_phonemes is not None:
            print(word, " ".join(dict_phonemes))

        if not args.quiet:
            if map_exists:
                # Map to espeak phonemes
                phoneme_map = dict(
                    re.split(r"\s+", line.strip(), maxsplit=1)
                    for line in map_path.read_text().splitlines()
                )

                espeak_phonemes = [phoneme_map[p] for p in dict_phonemes]
            else:
                espeak_phonemes = dict_phonemes

            # Speak with espeak
            espeak_str = "".join(espeak_phonemes)
            espeak_cmd = ["espeak", "-s", "80", f"[[{espeak_str}]]"]
            logger.debug(espeak_cmd)
            subprocess.check_call(espeak_cmd)

            time.sleep(args.delay)


# -----------------------------------------------------------------------------


def generate(args: argparse.Namespace, profile_dir: Path, profile) -> None:
    import pywrapfst as fst
    from voice2json.train.jsgf2fst import fstprintall

    # Load settings
    intent_fst_path = ppath(
        profile, profile_dir, "intent-recognition.intent-fst", "intent.fst"
    )

    # Load intent finite state transducer
    intent_fst = fst.Fst.read(str(intent_fst_path))

    # Generate samples
    rand_fst = fst.randgen(intent_fst, npath=args.samples)

    # Print samples
    fstprintall(rand_fst, out_file=sys.stdout, exclude_meta=(not args.meta))


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
