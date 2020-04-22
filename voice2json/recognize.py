"""Intent recognition methods."""
import argparse
import dataclasses
import gzip
import json
import logging
import os
import sys

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
    # stop_words_path = core.ppath("intent-recognition.stop-words", "stop_words.txt")
    fuzzy = pydash.get(core.profile, "intent-recognition.fuzzy", True)

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
                tokens = rhasspynlu.replace_numbers(tokens, language=language_code)

            # Recognize intent
            recognitions = rhasspynlu.recognize(
                tokens, intent_graph, fuzzy=fuzzy, word_transform=word_transform
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
