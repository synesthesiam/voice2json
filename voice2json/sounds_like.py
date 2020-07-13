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

                # line -> alternatives -> phoneme sequence
                known_phonemes: typing.List[typing.List[typing.List[str]]] = []

                # ongoing phoneme sequence
                current_phonemes: typing.List[str] = []

                # Process space-separated tokens
                for known_word in known_words:
                    if known_word.startswith("/"):
                        # Begin literal phoneme string
                        # /P1 P2 P3/
                        in_phoneme = True
                        known_word = known_word[1:]
                        current_phonemes = []

                    end_slash = known_word.endswith("/")
                    if end_slash:
                        # End literal phoneme string
                        # /P1 P2 P3/
                        known_word = known_word[:-1]

                    if in_phoneme:
                        # Literal phonemes
                        # P_N of /P1 P2 P3/
                        current_phonemes.append(known_word)
                    else:
                        # Check for >part<ial word
                        partial_match = _SOUNDS_LIKE_PARTIAL.match(known_word)
                        if partial_match:
                            partial_prefix, partial_body = (
                                partial_match.group(1),
                                partial_match.group(2),
                            )

                            if not g2p_alignment:
                                # Need to load g2p alignment corpus
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

                            # Add all possible alignments (phoneme sequences) as alternatives
                            known_phonemes.append(list(aligned_phonemes))
                        else:
                            # Known word with one or more pronunciations
                            known_prons = get_nth_word(pronunciations, known_word)
                            assert known_prons, f"No pronunciations for {known_word}"

                            # Add all pronunciations as alternatives
                            known_phonemes.append(known_prons)

                    if end_slash:
                        in_phoneme = False
                        if current_phonemes:
                            known_phonemes.append([current_phonemes])

                # Collect pronunciations from known words
                # word_prons: typing.List[typing.List[typing.List[str]]] = []
                for word_phonemes in itertools.product(*known_phonemes):
                    # Generate all possible pronunciations.
                    word_pron = list(itertools.chain(*word_phonemes))
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
    word_index: typing.Optional[int] = None
    match = _SOUNDS_LIKE_WORD_N.match(word)
    if match:
        # word(N)
        word, word_index = (match.group(1), int(match.group(2)))

    # Loop through possible alignments for this word
    for io_index, inputs_outputs in enumerate(g2p_alignment.get(word, [])):
        if (word_index is not None) and (word_index != (io_index + 1)):
            continue

        can_match = True
        prefix_chars = list(prefix)
        body_chars = list(body)

        phonemes = []
        for word_input, word_output in inputs_outputs:
            word_input = list(word_input)
            word_output = list(word_output)

            while prefix_chars and word_input:
                # Exhaust characters before desired word segment first
                if word_input[0] != prefix_chars[0]:
                    can_match = False
                    break

                prefix_chars = prefix_chars[1:]
                word_input = word_input[1:]

            while body_chars and word_input:
                # Match desired word segment
                if word_input[0] != body_chars[0]:
                    can_match = False
                    break

                body_chars = body_chars[1:]
                word_input = word_input[1:]

                if word_output:
                    phonemes.append(word_output[0])
                    word_output = word_output[1:]

            if not can_match or not body_chars:
                # Mismatch or done with word segment
                break

        if can_match and phonemes:
            yield phonemes


def get_nth_word(
    pronunciations: PronunciationsType, word: str
) -> typing.List[typing.List[str]]:
    """Get all pronunciations for a word or a single(n) pronunciation."""
    # Check for explicit word index (1-based)
    word_index: typing.Optional[int] = None
    match = _SOUNDS_LIKE_WORD_N.match(word)
    if match:
        # word(N)
        word, word_index = (match.group(1), int(match.group(2)))

    known_prons = pronunciations.get(word, [])
    if (not known_prons) or (word_index is None):
        # Add all known pronunciations
        return known_prons

    # Add indexed word only.
    # Clip to within bounds of list.
    i = min(max(1, word_index), len(known_prons)) - 1
    return [known_prons[i]]
