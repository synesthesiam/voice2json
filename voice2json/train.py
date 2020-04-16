import logging
import subprocess
import typing
from collections import defaultdict
from enum import Enum
from pathlib import Path

import pydash
import rhasspynlu
from rhasspynlu.jsgf import Expression, Word
from rhasspynlu.g2p import PronunciationsType

from .utils import ppath as utils_ppath, read_dict

_LOGGER = logging.getLogger("voice2json.train")


class AcousticModelType(str, Enum):
    POCKETSPHINX = "pocketsphinx"
    KALDI = "kaldi"
    JULIUS = "julius"
    DEEPSPEECH = "deepspeech"


class WordCasing(str, Enum):
    DEFAULT = "default"
    UPPER = "upper"
    LOWER = "lower"
    IGNORE = "ignore"


def train_profile(profile_dir: Path, profile: typing.Dict[str, typing.Any]) -> None:

    # Compact
    def ppath(query, default=None):
        return utils_ppath(profile, profile_dir, query, default)

    language_code = pydash.get(profile, "language.code", "en-US")

    sentences_ini = ppath("training.sentences-file", "sentences.ini")
    slots_dir = ppath("training.slots-directory", "slots")
    slot_programs = ppath("training.slots-directory", "slot_programs")

    # Profile files that are split into parts and gzipped
    large_paths = [Path(p) for p in pydash.get(profile, "training.large-files", [])]

    # -------------------
    # Speech to text
    # -------------------
    base_dictionary = ppath("training.base-dictionary", "base_dictionary.txt")
    custom_words = ppath("training.custom-words-file", "custom_words.txt")

    acoustic_model = ppath("training.acoustic-model", "acoustic_model")
    acoustic_model_type = pydash.get(
        profile, "training.acoustic-model-type", AcousticModelType.POCKETSPHINX
    )

    # Replace numbers with words
    replace_numbers = bool(pydash.get(profile, "training.replace-numbers", True))

    # ignore/upper/lower
    word_casing = pydash.get(profile, "training.word-casing", WordCasing.IGNORE)

    # -------------------
    # Grapheme to phoneme
    # -------------------
    g2p_model = ppath("training.grapheme-to-phoneme-model", "g2p.fst")

    # default/ignore/upper/lower
    g2p_word_casing = pydash.get(profile, "training.g2p-word-casing", word_casing)

    # -------
    # Outputs
    # -------
    dictionary_path = ppath("training.dictionary", "dictionary.txt")
    language_model_path = ppath("training.language-model", "language_model.txt")
    intent_graph_path = ppath("training.intent-graph", "intent.pickle.gz")
    vocab_path = ppath("training.vocabulary-file", "vocab.txt")
    unknown_words_path = ppath("training.unknown-words-file", "unknown_words.txt")

    # -------------------------------------------------------------------------
    # 1. Reassemble large files
    # -------------------------------------------------------------------------

    for target_path in large_paths:
        gzip_path = Path(str(target_path) + ".gz")
        part_paths = sorted(list(gzip_path.parent.glob(f"{gzip_path.name}.part-*")))
        if part_paths:
            # Concatenate paths to together
            cat_command = ["cat"] + [str(p) for p in part_paths]
            _LOGGER.debug(cat_command)

            with open(gzip_path, "wb") as gzip_file:
                subprocess.run(cat_command, check=True, stdout=gzip_file)

        if gzip_path.is_file():
            # Unzip single file
            unzip_command = ["gunzip", "-f", "--stdout", str(gzip_path)]
            _LOGGER.debug(unzip_command)

            with open(target_path, "wb") as target_file:
                subprocess.run(unzip_command, check=True, stdout=target_file)

            # Delete zip file
            gzip_path.unlink()

        # Delete unneeded .gz-part files
        for part_path in part_paths:
            part_path.unlink()

    # -------------------------------------------------------------------------
    # 2. Generate intent graph
    # -------------------------------------------------------------------------

    # Parse JSGF sentences
    _LOGGER.debug("Parsing %s", sentences_ini)
    intents = rhasspynlu.parse_ini(sentences_ini)

    # Split into sentences and rule/slot replacements
    sentences, replacements = rhasspynlu.ini_jsgf.split_rules(intents)

    word_transform = None
    if word_casing == WordCasing.UPPER:
        word_transform = str.upper
    elif word_casing == WordCasing.LOWER:
        word_transform = str.lower

    word_visitor: typing.Optional[
        typing.Callable[[Expression], typing.Union[bool, Expression]]
    ] = None

    if word_transform:
        # Apply transformation to words

        def transform_visitor(word: Expression):
            if isinstance(word, Word):
                assert word_transform
                new_text = word_transform(word.text)

                # Preserve case by using original text as substition
                if (word.substitution is None) and (new_text != word.text):
                    word.substitution = word.text

                word.text = new_text

            return word

        word_visitor = transform_visitor

    # Apply case/number transforms
    if word_visitor or replace_numbers:
        for intent_sentences in sentences.values():
            for sentence in intent_sentences:
                if replace_numbers:
                    # Replace number ranges with slot references
                    # type: ignore
                    rhasspynlu.jsgf.walk_expression(
                        sentence, rhasspynlu.number_range_transform, replacements
                    )

                if word_visitor:
                    # Do case transformation
                    # type: ignore
                    rhasspynlu.jsgf.walk_expression(
                        sentence, word_visitor, replacements
                    )

    # Load slot values
    slot_replacements = rhasspynlu.get_slot_replacements(
        intents,
        slots_dirs=[slots_dir],
        slot_programs_dirs=[slot_programs],
        slot_visitor=word_visitor,
    )

    # Merge with existing replacements
    for slot_key, slot_values in slot_replacements.items():
        replacements[slot_key] = slot_values

    if replace_numbers:
        # Do single number transformations
        for intent_sentences in sentences.values():
            for sentence in intent_sentences:
                rhasspynlu.jsgf.walk_expression(
                    sentence,
                    lambda w: rhasspynlu.number_transform(w, language_code),
                    replacements,
                )

    # Convert to directed graph
    intent_graph = rhasspynlu.sentences_to_graph(sentences, replacements=replacements)

    # Convert to gzipped pickle
    intent_graph_path.parent.mkdir(exist_ok=True)
    with open(intent_graph_path, mode="wb") as intent_graph_file:
        rhasspynlu.graph_to_gzip_pickle(intent_graph, intent_graph_file)

    _LOGGER.debug("Wrote intent graph to %s", intent_graph_path)

    pronunciations: PronunciationsType = defaultdict(list)

    def load_pronunciations() -> PronunciationsType:
        for dict_path in [base_dictionary, custom_words]:
            _LOGGER.debug("Loading base dictionary from %s", dict_path)
            with open(dict_path, "r") as dict_file:
                rhasspynlu.g2p.read_pronunciations(dict_file, word_dict=pronunciations)

    g2p_word_transform = None
    if g2p_word_casing == WordCasing.UPPER:
        g2p_word_transform = str.upper
    elif g2p_word_casing == WordCasing.LOWER:
        g2p_word_transform = str.lower

    if acoustic_model_type == AcousticModelType.POCKETSPHINX:
        import rhasspyasr_pocketsphinx

        load_pronunciations()
        rhasspyasr_pocketsphinx.train(
            intent_graph,
            dictionary_path,
            language_model_path,
            pronunciations,
            dictionary_word_transform=word_transform,
            g2p_model=g2p_model,
            g2p_word_transform=g2p_word_transform,
            missing_words_path=unknown_words_path,
        )
