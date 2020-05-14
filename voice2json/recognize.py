"""Intent recognition methods."""
import argparse
import dataclasses
import gzip
import io
import json
import logging
import os
import subprocess
import sys
import typing
from pathlib import Path

import pydash

from .core import Voice2JsonCore
from .utils import print_json

_LOGGER = logging.getLogger("voice2json.recognize")

# -----------------------------------------------------------------------------


async def recognize(args: argparse.Namespace, core: Voice2JsonCore) -> None:
    """Recognize intent from sentence(s)."""
    import networkx as nx
    import rhasspynlu
    from .train import WordCasing

    # Make sure profile has been trained
    assert core.check_trained(), "Not trained"

    # Load settings
    language_code = pydash.get(core.profile, "language.code", "en-US")
    word_casing = WordCasing(
        pydash.get(core.profile, "training.word-casing", "ignore").lower()
    )
    intent_graph_path = core.ppath("training.intent-graph", "intent.pickle.gz")
    converters_dir = core.ppath("training.converters-directory", "converters")
    stop_words_path = core.ppath("intent-recognition.stop-words", "stop_words.txt")
    fuzzy = pydash.get(core.profile, "intent-recognition.fuzzy", True)

    # Load stop words
    stop_words: typing.Optional[typing.Set[str]] = None
    if stop_words_path and stop_words_path.is_file():
        stop_words = set()
        with open(stop_words_path, "r") as stop_words_file:
            for line in stop_words_file:
                line = line.strip()
                if line:
                    stop_words.add(line)

    # Load converters
    extra_converters: typing.Optional[typing.Dict[str, typing.Any]] = {}
    if converters_dir:
        extra_converters = load_converters(converters_dir)

    # Case transformation for input words
    word_transform = None
    if word_casing == WordCasing.UPPER:
        word_transform = str.upper
    elif word_casing == WordCasing.LOWER:
        word_transform = str.lower

    if args.sentence:
        sentences = args.sentence
    else:
        if os.isatty(sys.stdin.fileno()):
            print("Reading sentences from stdin", file=sys.stderr)

        sentences = sys.stdin

    # Whitelist function for intents
    if args.intent_filter:
        args.intent_filter = set(args.intent_filter)

    def intent_filter(intent_name: str) -> bool:
        """Filter out intents."""
        if args.intent_filter:
            return intent_name in args.intent_filter

        return True

    # Load intent graph
    _LOGGER.debug("Loading %s", intent_graph_path)
    with gzip.GzipFile(intent_graph_path, mode="rb") as graph_gzip:
        intent_graph = nx.readwrite.gpickle.read_gpickle(graph_gzip)

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
            tokens = text.split()

            if args.replace_numbers:
                tokens = list(
                    rhasspynlu.replace_numbers(tokens, language=language_code)
                )

            # Recognize intent
            recognitions = rhasspynlu.recognize(
                tokens,
                intent_graph,
                fuzzy=fuzzy,
                # stop_words=stop_words,
                word_transform=word_transform,
                extra_converters=extra_converters,
                intent_filter=intent_filter,
            )

            if recognitions:
                # Use first recognition
                recognition = recognitions[0]
            else:
                # Recognition failure
                recognition = rhasspynlu.intent.Recognition.empty()

            result = dataclasses.asdict(recognition)

            # Add slots
            result["slots"] = {e.entity: e.value for e in recognition.entities}

            # Merge with input object
            for key, value in result.items():
                if (key not in sentence_object) or (value is not None):
                    sentence_object[key] = value

            if not sentence_object["text"]:
                sentence_object["text"] = text

            # Keep text from transcription
            sentence_object["raw_text"] = text

            if args.perplexity:
                # Compute perplexity of input text for one or more language
                # models (stored in FST binary format).
                perplexity = {}
                for lm_fst_path in args.perplexity:
                    try:
                        perplexity[lm_fst_path] = rhasspynlu.arpa_lm.get_perplexity(
                            text, lm_fst_path, debug=args.debug
                        )
                    except Exception:
                        _LOGGER.exception(lm_fst_path)

                sentence_object["perplexity"] = perplexity

            print_json(sentence_object)
    except KeyboardInterrupt:
        pass


# -----------------------------------------------------------------------------


class CommandLineConverter:
    """Command-line converter for intent recognition"""

    def __init__(self, name: str, command_path: typing.Union[str, Path]):
        self.name = name
        self.command_path = Path(command_path)

    def __call__(self, *args, converter_args=None):
        """Runs external program to convert JSON values"""
        converter_args = converter_args or []
        proc = subprocess.Popen(
            [str(self.command_path)] + converter_args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            universal_newlines=True,
        )

        with io.StringIO() as input_file:
            for arg in args:
                json.dump(arg, input_file)

            stdout, _ = proc.communicate(input=input_file.getvalue())

            return [json.loads(line) for line in stdout.splitlines() if line.strip()]


def load_converters(
    converters_dir: typing.Union[str, Path]
) -> typing.Dict[str, CommandLineConverter]:
    """Load user-defined converters"""
    converters: typing.Dict[str, CommandLineConverter] = {}
    converters_dir = Path(converters_dir)

    if converters_dir.is_dir():
        _LOGGER.debug("Loading converters from %s", converters_dir)
        for converter_path in converters_dir.glob("**/*"):
            if not converter_path.is_file():
                continue

            # Retain directory structure in name
            converter_name = str(
                converter_path.relative_to(converters_dir).with_suffix("")
            )

            # Run converter as external program.
            # Input arguments are encoded as JSON on individual lines.
            # Output values should be encoded as JSON on individual lines.
            converter = CommandLineConverter(converter_name, converter_path)

            # Key off name without file extension
            converters[converter_name] = converter

            _LOGGER.debug("Loaded converter %s from %s", converter_name, converter_path)

    return converters
