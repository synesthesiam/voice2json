#!/usr/bin/env python3
import logging

logger = logging.getLogger("vocab_dict")

import os
import sys
from pathlib import Path
from typing import Iterable, Optional, List, Dict, TextIO, Set

from voice2json.utils import read_dict

FORMAT_CMU = "cmu"
FORMAT_JULIUS = "julius"


def make_dict(
    vocab_path: Path,
    dictionary_paths: Iterable[Path],
    dictionary_file: TextIO,
    unknown_path: Optional[Path] = None,
    upper: bool = False,
    lower: bool = False,
    no_number: bool = False,
    dictionary_format: str = FORMAT_CMU,
    silence_words: Set[str] = set(["<s>", "</s>"]),
    merge_rule: str = "all",
) -> List[str]:
    transform = lambda w: w
    if upper:
        transform = lambda w: w.upper()
        logger.debug("Forcing upper-case")
    elif lower:
        transform = lambda w: w.lower()
        logger.debug("Forcing lower-case")

    is_julius = dictionary_format == FORMAT_JULIUS

    # Read dictionaries
    word_dict: Dict[str, List[str]] = {}
    for dict_path in dictionary_paths:
        if os.path.exists(dict_path):
            logger.debug(f"Loading dictionary from {dict_path}")
            with open(dict_path, "r") as dict_file:
                read_dict(
                    dict_file,
                    word_dict,
                    transform=transform,
                    silence_words=silence_words,
                )

    # Resolve vocabulary
    words_needed: Set[str] = set()
    with open(vocab_path, "r") as vocab_file:
        for word in vocab_file:
            word = word.strip()
            if len(word) == 0:
                continue

            word = transform(word)
            words_needed.add(word)

    logger.debug(f"Loaded {len(words_needed)} word(s) from {vocab_path}")

    # Add silence words
    words_needed.update(silence_words)

    # Write output dictionary
    merge_first = merge_rule == "first"
    words_in_dict: Set[str] = set()
    unknown_words: List[str] = []

    for word in sorted(words_needed):
        if (word not in word_dict) and (word not in silence_words):
            unknown_words.append(word)
            continue

        for i, pronounce in enumerate(word_dict.get(word, [])):
            if merge_first and (word in words_in_dict):
                # Only use first pronunciation when merge_rule is "first"
                continue

            if is_julius:
                # Julius format
                # word [word] P1 P2 P3
                print(word, f"[{word}]", pronounce, file=dictionary_file)
            else:
                # CMU format
                # word P1 P2 P3
                # word(N) P1 P2 P3
                if (i < 1) or no_number:
                    print(word, pronounce, file=dictionary_file)
                else:
                    print("%s(%s)" % (word, i + 1), pronounce, file=dictionary_file)

            words_in_dict.add(word)

    # -------------------------------------------------------------------------

    if len(unknown_words) > 0:
        logger.warning(f"{len(unknown_words)} word(s) are unknown")
        logger.warning(",".join(unknown_words))

        # Write unknown words
        if unknown_path:

            with open(unknown_path, "w") as unknown_file:
                for word in unknown_words:
                    print(word, file=unknown_file)

            logger.debug(f"Wrote unknown words to {unknown_path}")

    return unknown_words
