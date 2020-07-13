"""Methods for creating phonetic pronunciations from existing words and word segments."""
import itertools
import logging
import re
import typing
from collections import defaultdict
from pathlib import Path

from rhasspynlu.g2p import PronunciationAction, PronunciationsType

_LOGGER = logging.getLogger("voice2json.sounds_like")

G2PAlignmentType = typing.Dict[
    str, typing.List[typing.List[typing.Tuple[typing.List[str], typing.List[str]]]]
]
_SOUNDS_LIKE_WORD_N = re.compile(r"^([^(]+)\(([0-9]+)\)$")
_SOUNDS_LIKE_PARTIAL = re.compile(r"^([^>]*)>([^<]+)<.*$")

# -----------------------------------------------------------------------------


def load_sounds_like(
    sounds_like: typing.Union[str, Path, typing.TextIO],
    pronunciations: PronunciationsType,
    action: PronunciationAction = PronunciationAction.APPEND,
    g2p_alignment: typing.Optional[G2PAlignmentType] = None,
    g2p_corpus: typing.Optional[Path] = None,
) -> typing.Optional[G2PAlignmentType]:
    """Loads file with unknown word pronunciations based on known words."""
    original_action = action

    # word -> [[(["graheme", ...], ["phoneme", ...])], ...]
    g2p_alignment = g2p_alignment or {}

    if isinstance(sounds_like, (str, Path)):
        sounds_like_file = open(sounds_like, "r")
    else:
        # TextIO
        sounds_like_file = sounds_like

    # File with <unknown_word> <known_word> [<known_word> ...]
    # Pronunciation is derived from phonemes of known words.
    # Phonemes can be included with the syntax /P1 P2/
    with sounds_like_file:
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

                            # Align graphemes with phonemes
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

    return g2p_alignment


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
