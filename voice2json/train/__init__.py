#!/usr/bin/env python3
import os
import re
import sys
import json
import argparse
import logging
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, Set, Iterable, Any, List
from collections import deque

import yaml
import pydash
import pywrapfst as fst
import networkx as nx
import doit

from doit import create_after

from voice2json.train.jsgf2fst import (
    get_grammar_dependencies,
    grammar_to_fsts,
    slots_to_fsts,
    make_intent_fst,
)

from voice2json.train.ini_jsgf import make_grammars
from voice2json.train.vocab_dict import make_dict, FORMAT_CMU, FORMAT_JULIUS
from voice2json.utils import ppath as utils_ppath, read_dict

logger = logging.getLogger("train")

# -----------------------------------------------------------------------------


def train_profile(profile_dir: Path, profile: Dict[str, Any]) -> None:

    # Compact
    def ppath(query, default=None):
        return utils_ppath(profile, profile_dir, query, default)

    # Inputs
    intent_whitelist = ppath("training.intent-whitelist", "intent_whitelist")
    sentences_ini = ppath("training.sentences-file", "sentences.ini")
    base_dictionary = ppath("training.base-dictionary", "base_dictionary.txt")
    base_language_model = ppath(
        "training.base-language-model", "base_language_model.txt"
    )
    base_language_model_fst = ppath(
        "training.base-language-model-fst", "base_language_model.fst"
    )
    base_language_model_weight = float(
        pydash.get(profile, "training.base-language-model-weight", 0)
    )
    custom_words = ppath("training.custom-words-file", "custom_words.txt")
    g2p_model = ppath("training.grapheme-to-phoneme-model", "g2p.fst")
    acoustic_model = ppath("training.acoustic-model", "acoustic_model")
    acoustic_model_type = pydash.get(
        profile, "training.acoustic-model-type", "pocketsphinx"
    ).lower()

    # ignore/upper/lower
    word_casing = pydash.get(profile, "training.word-casing", "ignore").lower()

    # default/ignore/upper/lower
    g2p_word_casing = pydash.get(
        profile, "training.g2p-word-casing", word_casing
    ).lower()

    # all/first
    dict_merge_rule = pydash.get(
        profile, "training.dictionary-merge-rule", "all"
    ).lower()

    # Kaldi
    kaldi_graph_dir = ppath("training.kaldi.graph-directory") or (
        acoustic_model / "graph"
    )
    kaldi_model_type = pydash.get(profile, "training.kaldi.model-type", "")

    # Large paths
    large_paths = [Path(p) for p in pydash.get(profile, "training.large-files", [])]

    # Outputs
    dictionary = ppath("training.dictionary", "dictionary.txt")
    language_model = ppath("training.language-model", "language_model.txt")
    intent_fst = ppath("training.intent-fst", "intent.fst")
    vocab = ppath("training.vocabulary-file", "vocab.txt")
    unknown_words = ppath("training.unknown-words-file", "unknown.txt")
    grammar_dir = ppath("training.grammar-directory", "grammars")
    fsts_dir = ppath("training.fsts-directory", "fsts")
    slots_dir = ppath("training.slots-directory", "slots")

    # -----------------------------------------------------------------------------

    # Create cache directories
    for dir_path in [grammar_dir, fsts_dir]:
        dir_path.mkdir(parents=True, exist_ok=True)

    # -----------------------------------------------------------------------------

    # Set of used intents
    intents: Set[str] = set()
    whitelist = None

    # Default to using all intents
    intents.update(_get_intents(sentences_ini))

    # Check if intent whitelist exists
    if intent_whitelist.exists():
        with open(intent_whitelist, "r") as whitelist_file:
            # Each line is an intent to use
            for line in whitelist_file:
                line = line.strip()
                if len(line) > 0:
                    if whitelist is None:
                        whitelist = []
                        intents.clear()

                    whitelist.append(line)
                    intents.add(line)

    # -----------------------------------------------------------------------------

    def do_reassemble(paths: List[Path], targets):
        with open(targets[0], "wb") as target_file:
            subprocess.run(["cat"] + [str(path) for path in paths], stdout=target_file)

    def task_reassemble_files():
        for path in large_paths:
            gzip_path = Path(str(path) + ".gz")
            part_paths = sorted(list(gzip_path.parent.glob(f"{gzip_path.name}.part-*")))
            if len(part_paths) > 0:
                if gzip_path.exists():
                    # Delete unneeded .gz-part files
                    for part_path in part_paths:
                        part_path.unlink()
                else:
                    # Assemble the file. We can't delete the parts here, since doit gets upset.
                    yield {
                        "name": f"reassemble_{gzip_path.name}",
                        "file_dep": part_paths,
                        "targets": [gzip_path],
                        "actions": [(do_reassemble, [part_paths])],
                    }

    # -----------------------------------------------------------------------------

    @create_after(executed="reassemble_files")
    def task_unzip_files():
        for path in large_paths:
            gzip_path = Path(str(path) + ".gz")
            if gzip_path.exists():
                if path.exists():
                    # Delete unneeded .gz file
                    gzip_path.unlink()
                else:
                    # Unzip the file. We can't delete it here, since doit gets upset.
                    yield {
                        "name": f"unzip_{path.name}",
                        "file_dep": [gzip_path],
                        "targets": [path],
                        "actions": [
                            "gunzip -f --stdout %(dependencies)s > %(targets)s"
                        ],
                    }

    # -----------------------------------------------------------------------------

    @create_after(executed="unzip_files")
    def task_grammars():
        """Transforms sentences.ini into JSGF grammars, one per intent."""
        maybe_deps = []
        if intent_whitelist.exists():
            maybe_deps.append(intent_whitelist)

        def ini_to_grammars(targets):
            with open(sentences_ini, "r") as sentences_file:
                make_grammars(sentences_file, grammar_dir, whitelist=whitelist)

        return {
            "file_dep": [sentences_ini] + maybe_deps,
            "targets": [grammar_dir / f"{intent}.gram" for intent in intents],
            "actions": [ini_to_grammars],
        }

    # -----------------------------------------------------------------------------

    def do_slots_to_fst(slot_names, targets):
        # Extra arguments for word casing
        kwargs = {}
        if word_casing == "upper":
            kwargs["upper"] = True
        elif word_casing == "lower":
            kwargs["lower"] = True

        slot_fsts = slots_to_fsts(slots_dir, slot_names=slot_names, **kwargs)
        for slot_name, slot_fst in slot_fsts.items():
            # Slot name will already have "$"
            slot_fst.write(str(fsts_dir / f"{slot_name}.fst"))

    def do_grammar_to_fsts(
        grammar_path: Path, replace_fst_paths: Dict[str, Path], targets
    ):
        # Load dependent FSTs
        replace_fsts = {
            replace_name: fst.Fst.read(str(replace_path))
            for replace_name, replace_path in replace_fst_paths.items()
        }

        # Extra arguments for word casing
        kwargs = {}
        if word_casing == "upper":
            kwargs["upper"] = True
        elif word_casing == "lower":
            kwargs["lower"] = True

        grammar = grammar_path.read_text()
        listener = grammar_to_fsts(grammar, replace_fsts=replace_fsts, **kwargs)
        grammar_name = listener.grammar_name

        # Write FST for each JSGF rule
        for rule_name, rule_fst in listener.fsts.items():
            fst_path = fsts_dir / f"{rule_name}.fst"
            rule_fst.write(str(fst_path))

        # Write FST for main grammar rule
        grammar_fst_path = fsts_dir / f"{grammar_name}.fst"
        listener.grammar_fst.write(str(grammar_fst_path))

    # -----------------------------------------------------------------------------

    def do_grammar_dependencies(grammar_path: Path, targets):
        grammar = grammar_path.read_text()
        grammar_deps = get_grammar_dependencies(grammar).graph
        graph_json = nx.readwrite.json_graph.node_link_data(grammar_deps)
        with open(targets[0], "w") as graph_file:
            json.dump(graph_json, graph_file)

    @create_after(executed="grammars")
    def task_grammar_dependencies():
        """Creates grammar dependency graphs from JSGF grammars and relevant slots."""

        for intent in intents:
            grammar_path = grammar_dir / f"{intent}.gram"
            yield {
                "name": intent + "_dependencies",
                "file_dep": [grammar_path],
                "targets": [str(grammar_path) + ".json"],
                "actions": [(do_grammar_dependencies, [grammar_path])],
            }

    # -----------------------------------------------------------------------------

    @create_after(executed="grammar_dependencies")
    def task_grammar_fsts():
        """Creates grammar FSTs from JSGF grammars and relevant slots."""
        used_slots: Set[str] = set()

        for intent in intents:
            grammar_path = grammar_dir / f"{intent}.gram"
            grammar_dep_path = str(grammar_path) + ".json"

            # Load dependency graph
            with open(grammar_dep_path, "r") as graph_file:
                graph_data = json.load(graph_file)
                grammar_deps = nx.readwrite.json_graph.node_link_graph(graph_data)

            rule_names: Set[str] = set()
            replace_fst_paths: Dict[str, Path] = {}

            # Process dependencies
            for node, data in grammar_deps.nodes(data=True):
                node_type = data["type"]

                if node_type == "slot":
                    # Strip "$"
                    slot_name = node[1:]
                    used_slots.add(slot_name)

                    # Path to slot FST
                    replace_fst_paths[node] = fsts_dir / f"{node}.fst"
                elif node_type == "remote rule":
                    # Path to rule FST
                    replace_fst_paths[node] = fsts_dir / f"{node}.fst"
                elif node_type == "local rule":
                    rule_names.add(node)

            # All rule/grammar FSTs that will be generated
            grammar_fst_paths = [
                fsts_dir / f"{rule_name}.fst" for rule_name in rule_names
            ]
            grammar_fst_paths.append(fsts_dir / f"{intent}.fst")

            yield {
                "name": intent + "_fst",
                "file_dep": [grammar_path, grammar_dep_path]
                + list(replace_fst_paths.values()),
                "targets": grammar_fst_paths,
                "actions": [(do_grammar_to_fsts, [grammar_path, replace_fst_paths])],
            }

        # slots -> FST
        if len(used_slots) > 0:
            yield {
                "name": "slot_fsts",
                "file_dep": [slots_dir / slot_name for slot_name in used_slots],
                "targets": [fsts_dir / f"${slot_name}.fst" for slot_name in used_slots],
                "actions": [(do_slots_to_fst, [used_slots])],
            }

    # -----------------------------------------------------------------------------

    def do_intent_fst(intents: Iterable[str], targets):
        intent_fsts = {
            intent: fst.Fst.read(str(fsts_dir / f"{intent}.fst")) for intent in intents
        }
        intent_fst = make_intent_fst(intent_fsts)
        intent_fst.write(targets[0])

    @create_after(executed="grammar_fsts")
    def task_intent_fst():
        """Merges grammar FSTs into single intent.fst."""
        return {
            "file_dep": [fsts_dir / f"{intent}.fst" for intent in intents],
            "targets": [intent_fst],
            "actions": [(do_intent_fst, [intents])],
        }

    # -----------------------------------------------------------------------------

    @create_after(executed="intent_fst")
    def task_language_model():
        """Creates an ARPA language model from intent.fst."""

        if base_language_model_weight > 0:
            yield {
                "name": "base_lm_to_fst",
                "file_dep": [base_language_model],
                "targets": [base_language_model_fst],
                "actions": ["ngramread --ARPA %(dependencies)s %(targets)s"],
            }

        # FST -> n-gram counts
        intent_counts = str(intent_fst) + ".counts"
        yield {
            "name": "intent_counts",
            "file_dep": [intent_fst],
            "targets": [intent_counts],
            "actions": ["ngramcount %(dependencies)s %(targets)s"],
        }

        # n-gram counts -> model
        intent_model = str(intent_fst) + ".model"
        yield {
            "name": "intent_model",
            "file_dep": [intent_counts],
            "targets": [intent_model],
            "actions": ["ngrammake %(dependencies)s %(targets)s"],
        }

        if base_language_model_weight > 0:
            merged_model = str(intent_model) + ".merge"

            # merge
            yield {
                "name": "lm_merge",
                "file_dep": [base_language_model_fst, intent_model],
                "targets": [merged_model],
                "actions": [
                    f"ngrammerge --alpha={base_language_model_weight} %(dependencies)s %(targets)s"
                ],
            }

            intent_model = merged_model

        # model -> ARPA
        yield {
            "name": "intent_arpa",
            "file_dep": [intent_model],
            "targets": [language_model],
            "actions": ["ngramprint --ARPA %(dependencies)s > %(targets)s"],
        }

    # -----------------------------------------------------------------------------

    def do_vocab(targets):
        with open(targets[0], "w") as vocab_file:
            input_symbols = fst.Fst.read(str(intent_fst)).input_symbols()
            for i in range(input_symbols.num_symbols()):
                symbol = input_symbols.find(i).decode().strip()
                if not (symbol.startswith("__") or symbol.startswith("<")):
                    print(symbol, file=vocab_file)

            if base_language_model_weight > 0:
                # Add all words from base dictionary
                with open(base_dictionary, "r") as dict_file:
                    for word in read_dict(dict_file):
                        print(word, file=vocab_file)

    @create_after(executed="language_model")
    def task_vocab():
        """Writes all vocabulary words to a file from intent.fst."""
        return {"file_dep": [intent_fst], "targets": [vocab], "actions": [do_vocab]}

    # -----------------------------------------------------------------------------

    def do_dict(dictionary_paths: Iterable[Path], targets):
        with open(targets[0], "w") as dictionary_file:
            if unknown_words.exists():
                unknown_words.unlink()

            dictionary_format = FORMAT_CMU
            if acoustic_model_type == "julius":
                dictionary_format = FORMAT_JULIUS

            # Extra arguments for word casing
            kwargs = {}
            if word_casing == "upper":
                kwargs["upper"] = True
            elif word_casing == "lower":
                kwargs["lower"] = True

            make_dict(
                vocab,
                dictionary_paths,
                dictionary_file,
                unknown_path=unknown_words,
                dictionary_format=dictionary_format,
                merge_rule=dict_merge_rule,
                **kwargs,
            )

            if unknown_words.exists() and g2p_model.exists():
                # Generate single pronunciation guesses
                logger.debug("Guessing pronunciations for unknown word(s)")

                g2p_proc = subprocess.Popen(
                    [
                        "phonetisaurus-apply",
                        "--model",
                        str(g2p_model),
                        "--word_list",
                        str(unknown_words),
                        "--nbest",
                        "1",
                    ],
                    stdout=subprocess.PIPE,
                )

                g2p_transform = lambda w: w
                if g2p_word_casing == "upper":
                    g2p_transform = lambda w: w.upper()
                elif g2p_word_casing == "lower":
                    g2p_transform = lambda w: w.lower()

                # Append to dictionary and custom words
                with open(custom_words, "a") as words_file:
                    for line in g2p_proc.stdout:
                        line = line.decode().strip()
                        word, phonemes = re.split(r"\s+", line, maxsplit=1)
                        word = g2p_transform(word)
                        print(word, phonemes, file=dictionary_file)
                        print(word, phonemes, file=words_file)

    @create_after(executed="vocab")
    def task_vocab_dict():
        """Creates custom pronunciation dictionary based on desired vocabulary."""
        dictionary_paths = [base_dictionary]
        if custom_words.exists():
            # Custom dictionary goes first so that the "first" dictionary merge
            # rule will choose pronunciations from it.
            dictionary_paths.insert(0, custom_words)

        # Exclude dictionaries that don't exist
        dictionary_paths = [p for p in dictionary_paths if p.exists()]

        return {
            "file_dep": [vocab] + dictionary_paths,
            "targets": [dictionary],
            "actions": [(do_dict, [dictionary_paths])],
        }

    def do_marytts_dict(map_path, targets):
        # Load phoneme map
        phoneme_map = dict(
            re.split(r"\s+", line.strip(), maxsplit=1)
            for line in map_path.read_text().splitlines()
        )

        # Create directory for dictionary
        dict_path = Path(targets[0])
        dict_path.parent.mkdir(parents=True, exist_ok=True)

        # Read in custom speech dictionary
        with open(custom_words, "r") as custom_words_file:
            custom_dict = read_dict(custom_words_file)

        # Write custom MaryTTS dictionary
        with open(dict_path, "w") as dict_file:
            for word, prons in custom_dict.items():
                # Only use first pronunciation
                dict_phonemes = re.split(r"\s+", prons[0])

                # Map to MaryTTS phonemes
                marytts_phonemes = [phoneme_map[p] for p in dict_phonemes]
                phoneme_str = " ".join(marytts_phonemes)

                print(word, "|", phoneme_str, file=dict_file)

    @create_after(executed="vocab_dict")
    def task_marytts_dict():
        """Creates custom pronunciation dictionary for MaryTTS."""
        marytts_map_path = ppath(
            "text-to-speech.marytts.phoneme-map", "marytts_phonemes.txt"
        )

        marytts_dict_path = ppath("text-to-speech.marytts.dictionary-file", "")

        if (
            custom_words.exists()
            and marytts_map_path.exists()
            and (len(marytts_dict_path) > 0)
        ):
            return {
                "file_dep": [custom_words, marytts_map_path],
                "targets": [marytts_dict_path],
                "actions": [(do_marytts_dict, [marytts_map_path])],
            }

    # -----------------------------------------------------------------------------

    @create_after(executed="vocab_dict")
    def task_kaldi_train():
        """Creates HCLG.fst for a Kaldi nnet3 or gmm model."""
        if acoustic_model_type == "kaldi":
            return {
                "file_dep": [dictionary, language_model],
                "targets": [kaldi_graph_dir / "HCLG.fst"],
                "actions": [
                    [
                        "kaldi-train",
                        "--model-type",
                        kaldi_model_type,
                        "--model-dir",
                        acoustic_model,
                        "--dictionary",
                        dictionary,
                        "--language-model",
                        language_model,
                        "--graph-dir",
                        kaldi_graph_dir,
                    ]
                ],
            }

    # -----------------------------------------------------------------------------

    DOIT_CONFIG = {"action_string_formatting": "old"}

    # Monkey patch inspect to make doit work inside Pyinstaller.
    # It grabs the line numbers of functions probably for debugging reasons, but
    # PyInstaller doesn't seem to keep that information around.
    #
    # This better thing to do would be to create a custom TaskLoader.
    import inspect

    inspect.getsourcelines = lambda obj: [0, 0]

    # Run doit main
    doit.run(locals())


# -----------------------------------------------------------------------------

# Matches an ini header, e.g. [LightState]
intent_pattern = re.compile(r"^\[([^\]]+)\]")


def _get_intents(ini_path):
    """Yields the names of all intents in a sentences.ini file."""
    with open(ini_path, "r") as ini_file:
        for line in ini_file:
            line = line.strip()
            match = intent_pattern.match(line)
            if match:
                yield match.group(1)
