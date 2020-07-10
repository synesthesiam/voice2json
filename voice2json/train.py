"""Methods to train a voice2json profile."""
import asyncio
import itertools
import logging
import re
import typing
from collections import defaultdict
from enum import Enum
from pathlib import Path

import pydash
import rhasspynlu
from rhasspynlu.g2p import PronunciationAction, PronunciationsType
from rhasspynlu.jsgf import Expression, Word

from .utils import ppath as utils_ppath

_LOGGER = logging.getLogger("voice2json.train")

# -----------------------------------------------------------------------------


class AcousticModelType(str, Enum):
    """Support speech to text systems."""

    DUMMY = "dummy"
    POCKETSPHINX = "pocketsphinx"
    KALDI = "kaldi"
    JULIUS = "julius"
    DEEPSPEECH = "deepspeech"


class WordCasing(str, Enum):
    """Word casing transformation types."""

    DEFAULT = "default"
    UPPER = "upper"
    LOWER = "lower"
    IGNORE = "ignore"


# -----------------------------------------------------------------------------


async def train_profile(
    profile_dir: Path, profile: typing.Dict[str, typing.Any]
) -> None:
    """Re-generate speech/intent artifacts for profile."""

    # Compact
    def ppath(query, default=None):
        return utils_ppath(profile, profile_dir, query, default)

    language_code = pydash.get(profile, "language.code", "en-US")

    sentences_ini = ppath("training.sentences-file", "sentences.ini")
    slots_dir = ppath("training.slots-directory", "slots")
    slot_programs = ppath("training.slot-programs-directory", "slot_programs")

    # Profile files that are split into parts and gzipped
    large_paths = [Path(p) for p in pydash.get(profile, "training.large-files", [])]

    # -------------------
    # Speech to text
    # -------------------
    base_dictionary = ppath("training.base-dictionary", "base_dictionary.txt")
    custom_words = ppath("training.custom-words-file", "custom_words.txt")
    custom_words_action = PronunciationAction(
        pydash.get(profile, "training.custom-words-action", "append")
    )
    sounds_like = ppath("training.sounds-like-file", "sounds_like.txt")
    sounds_like_action = PronunciationAction(
        pydash.get(profile, "training.sounds-like-action", "append")
    )

    acoustic_model = ppath("training.acoustic-model", "acoustic_model")
    acoustic_model_type = AcousticModelType(
        pydash.get(profile, "training.acoustic-model-type", AcousticModelType.DUMMY)
    )

    # Replace numbers with words
    replace_numbers = bool(pydash.get(profile, "training.replace-numbers", True))

    # ignore/upper/lower
    word_casing = pydash.get(profile, "training.word-casing", WordCasing.IGNORE)

    # Large pre-built language model
    base_language_model_fst = ppath(
        "training.base-language-model-fst", "base_language_model.fst"
    )
    base_language_model_weight = float(
        pydash.get(profile, "training.base-language-model-weight", 0)
    )

    # -------------------
    # Grapheme to phoneme
    # -------------------
    g2p_model = ppath("training.grapheme-to-phoneme-model", "g2p.fst")
    g2p_corpus = ppath("training.grapheme-to-phoneme-corpus", "g2p.corpus")

    # default/ignore/upper/lower
    g2p_word_casing = pydash.get(profile, "training.g2p-word-casing", word_casing)

    # -------
    # Outputs
    # -------
    dictionary_path = ppath("training.dictionary", "dictionary.txt")
    language_model_path = ppath("training.language-model", "language_model.txt")
    language_model_fst_path = ppath("training.language-model-fst", "language_model.fst")
    mixed_language_model_fst_path = ppath(
        "training.mixed-language-model-fst", "mixed_language_model.fst"
    )
    intent_graph_path = ppath("training.intent-graph", "intent.pickle.gz")
    vocab_path = ppath("training.vocabulary-file", "vocab.txt")
    unknown_words_path = ppath("training.unknown-words-file", "unknown_words.txt")

    async def run(command: typing.List[str], **kwargs):
        """Run a command asynchronously."""
        process = await asyncio.create_subprocess_exec(*command, **kwargs)
        await process.wait()
        assert process.returncode == 0, "Command failed"

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
                await run(cat_command, stdout=gzip_file)

        if gzip_path.is_file():
            # Unzip single file
            unzip_command = ["gunzip", "-f", "--stdout", str(gzip_path)]
            _LOGGER.debug(unzip_command)

            with open(target_path, "wb") as target_file:
                await run(unzip_command, stdout=target_file)

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

    def load_pronunciations():
        for dict_path in [base_dictionary, custom_words]:
            if not dict_path.is_file():
                _LOGGER.warning("Skipping %s (does not exist)", dict_path)
                continue

            _LOGGER.debug("Loading base dictionary from %s", dict_path)
            with open(dict_path, "r") as dict_file:
                rhasspynlu.g2p.read_pronunciations(
                    dict_file, word_dict=pronunciations, action=custom_words_action
                )

        if sounds_like.is_file():
            load_sounds_like(
                sounds_like,
                pronunciations,
                action=sounds_like_action,
                g2p_corpus=g2p_corpus,
            )

    g2p_word_transform = None
    if g2p_word_casing == WordCasing.UPPER:
        g2p_word_transform = str.upper
    elif g2p_word_casing == WordCasing.LOWER:
        g2p_word_transform = str.lower

    if acoustic_model_type == AcousticModelType.POCKETSPHINX:
        # Pocketsphinx
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
            vocab_path=vocab_path,
            language_model_fst=language_model_fst_path,
            base_language_model_fst=base_language_model_fst,
            base_language_model_weight=base_language_model_weight,
            mixed_language_model_fst=mixed_language_model_fst_path,
        )
    elif acoustic_model_type == AcousticModelType.KALDI:
        # Kaldi
        import rhasspyasr_kaldi

        graph_dir = ppath("training.kaldi.graph-directory") or (
            acoustic_model / "graph"
        )

        load_pronunciations()
        rhasspyasr_kaldi.train(
            intent_graph,
            pronunciations,
            acoustic_model,
            graph_dir,
            dictionary_path,
            language_model_path,
            dictionary_word_transform=word_transform,
            g2p_model=g2p_model,
            g2p_word_transform=g2p_word_transform,
            missing_words_path=unknown_words_path,
            vocab_path=vocab_path,
            language_model_fst=language_model_fst_path,
            base_language_model_fst=base_language_model_fst,
            base_language_model_weight=base_language_model_weight,
            mixed_language_model_fst=mixed_language_model_fst_path,
        )
    elif acoustic_model_type == AcousticModelType.DEEPSPEECH:
        # DeepSpeech
        import rhasspyasr_deepspeech

        trie_path = ppath("training.deepspeech.trie", "trie")
        alphabet_path = ppath("training.deepspeech.alphabet", "model/alphabet.txt")

        rhasspyasr_deepspeech.train(
            intent_graph,
            language_model_path,
            trie_path,
            alphabet_path,
            vocab_path=vocab_path,
            language_model_fst=language_model_fst_path,
            base_language_model_fst=base_language_model_fst,
            base_language_model_weight=base_language_model_weight,
            mixed_language_model_fst=mixed_language_model_fst_path,
        )
    elif acoustic_model_type == AcousticModelType.JULIUS:
        # Julius
        from .julius import train as train_julius

        load_pronunciations()
        train_julius(
            intent_graph,
            dictionary_path,
            language_model_path,
            pronunciations,
            dictionary_word_transform=word_transform,
            silence_words={"<s>", "</s>"},
            g2p_model=g2p_model,
            g2p_word_transform=g2p_word_transform,
            missing_words_path=unknown_words_path,
            vocab_path=vocab_path,
            language_model_fst=language_model_fst_path,
            base_language_model_fst=base_language_model_fst,
            base_language_model_weight=base_language_model_weight,
            mixed_language_model_fst=mixed_language_model_fst_path,
        )
    else:
        _LOGGER.warning("Not training speech to text system (%s)", acoustic_model_type)


# -----------------------------------------------------------------------------

G2PAlignmentType = typing.Dict[
    str, typing.List[typing.List[typing.Tuple[typing.List[str], typing.List[str]]]]
]
_SOUNDS_LIKE_WORD_N = re.compile(r"^([^(]+)\(([0-9]+)\)$")
_SOUNDS_LIKE_PARTIAL = re.compile(r"^([^>]*)>([^<]+)<.*$")


def load_sounds_like(
    sounds_like: Path,
    pronunciations: PronunciationsType,
    action: PronunciationAction = PronunciationAction.APPEND,
    g2p_corpus: typing.Optional[Path] = None,
):
    """Loads file with unknown word pronunciations based on known words."""
    original_action = action

    # word -> [[(["graheme", ...], ["phoneme", ...])], ...]
    g2p_alignment: G2PAlignmentType = {}

    # File with <unknown_word> <known_word> [<known_word> ...]
    # Pronunciation is derived from phonemes of known words.
    # Phonemes can be included with the syntax /P1 P2/
    with open(sounds_like, "r") as sounds_like_file:
        for i, line in enumerate(sounds_like_file):
            line = line.strip()
            if not line:
                continue

            try:
                # Restore word action
                action = original_action

                # Parse line of <unknown> <known> [<known> ...]
                unknown_word, *known_words = line.split()
                assert known_words, f"No known words for {unknown_word}"

                # Identify literal phonemes
                in_phoneme = False
                known_words_phonemes: typing.List[typing.Tuple[bool, str]] = []
                for known_word in known_words:
                    if known_word.startswith("/"):
                        in_phoneme = True
                        known_word = known_word[1:]

                    end_slash = known_word.endswith("/")
                    if end_slash:
                        known_word = known_word[:-1]

                    if not in_phoneme:
                        # >part<ial word
                        partial_match = _SOUNDS_LIKE_PARTIAL.match(known_word)
                        if partial_match:
                            partial_prefix, partial_body = (
                                partial_match.group(1),
                                partial_match.group(2),
                            )

                            if not g2p_alignment:
                                assert (
                                    g2p_corpus
                                ), f"No G2P corpus given for partial word: {known_word}"
                                assert (
                                    g2p_corpus.is_file()
                                ), f"Missing G2P corpus for {known_word}: {g2p_corpus}"

                                g2p_alignment = load_g2p_corpus(g2p_corpus)
                                word = re.sub(r"[<>]", "", known_word)
                                aligned_phonemes = get_aligned_phonemes(
                                    g2p_alignment, word, partial_prefix, partial_body
                                )

                                for body_phonemes in aligned_phonemes:
                                    known_words_phonemes.extend(
                                        (True, p) for p in body_phonemes
                                    )

                                    # Only add first alignment
                                    break

                                continue

                    known_words_phonemes.append((in_phoneme, known_word))

                    if end_slash:
                        in_phoneme = False

                # Collect pronunciations from known words
                word_prons: typing.List[typing.List[typing.List[str]]] = []
                for is_phoneme, known_word in known_words_phonemes:
                    if is_phoneme:
                        # Add literal phoneme
                        word_prons.append([[known_word]])
                        continue

                    # Check for explicit word index (1-based)
                    word_index: typing.Optional[int] = None
                    match = _SOUNDS_LIKE_WORD_N.match(known_word)
                    if match:
                        # word(N)
                        known_word, word_index = match.group(1), int(match.group(2))

                    if known_word in pronunciations:
                        known_prons = pronunciations[known_word]
                        assert known_prons, f"No pronunciations for {known_word}"
                        if word_index is None:
                            # Add all known pronunciations
                            word_prons.append(known_prons)
                        else:
                            # Add indexed word only.
                            # Clip to within bounds of list.
                            i = min(max(1, word_index), len(known_prons)) - 1
                            word_prons.append([known_prons[i]])
                    else:
                        raise ValueError(
                            f"Unknown word used in sounds like for '{unknown_word}': {known_word}"
                        )

                # Generate all possible pronunciations.
                # There can be more than one generated pronunciation if one or
                # more known words have multiple pronunciations.
                for word_pron_tuple in itertools.product(*word_prons):
                    word_pron = list(itertools.chain(*word_pron_tuple))
                    has_word = unknown_word in pronunciations

                    # Handle according to custom words action
                    if has_word and (action == PronunciationAction.APPEND):
                        # Append to list of pronunciations
                        pronunciations[unknown_word].append(word_pron)
                    elif action == PronunciationAction.OVERWRITE_ONCE:
                        # Overwrite just once, then append
                        pronunciations[unknown_word] = [word_pron]
                        action = PronunciationAction.APPEND
                    else:
                        # Overwrite
                        pronunciations[unknown_word] = [word_pron]
            except Exception as e:
                _LOGGER.warning("load_sounds_like: %s (line %s)", e, i + 1)
                raise e


def load_g2p_corpus(g2p_corpus: Path) -> G2PAlignmentType:
    """Loads a grapheme to phoneme alignment corpus generated by Phonetisaurus."""
    g2p_alignment: G2PAlignmentType = defaultdict(list)

    _LOGGER.debug("Loading g2p corpus from %s", g2p_corpus)
    with open(g2p_corpus, "r") as corpus_file:
        for line in corpus_file:
            line = line.strip()
            if not line:
                continue

            word = ""
            inputs_outputs = []

            # Parse line
            parts = line.split()
            for part in parts:
                # Assume default delimiters:
                # } separates input/output
                # | separates input/output tokens
                # _ indicates empty output
                part_in, part_out = part.split("}")
                part_ins = part_in.split("|")
                if part_out == "_":
                    # Empty output
                    part_outs = []
                else:
                    part_outs = part_out.split("|")

                inputs_outputs.append((part_ins, part_outs))
                word += "".join(part_ins)

            # Add to pronunciations for word
            g2p_alignment[word].append(inputs_outputs)

    return g2p_alignment


def get_aligned_phonemes(
    g2p_alignment: G2PAlignmentType, word: str, prefix: str, body: str
) -> typing.Iterable[typing.List[str]]:
    """Yields lists of phonemes that comprise the body of the word. Prefix graphemes are skipped."""
    for inputs_outputs in g2p_alignment.get(word, []):
        can_match = True
        prefix_chars = list(prefix)
        body_chars = list(body)

        phonemes = []
        for word_input, word_output in inputs_outputs:
            word_input = list(word_input)
            word_output = list(word_output)

            while prefix_chars and word_input:
                if word_input[0] != prefix_chars[0]:
                    can_match = False
                    break

                prefix_chars = prefix_chars[1:]
                word_input = word_input[1:]

            while body_chars and word_input:
                if word_input[0] != body_chars[0]:
                    can_match = False
                    break

                body_chars = body_chars[1:]
                word_input = word_input[1:]

                if word_output:
                    phonemes.append(word_output[0])
                    word_output = word_output[1:]

            if not can_match or not body_chars:
                break

        if can_match and phonemes:
            yield phonemes
