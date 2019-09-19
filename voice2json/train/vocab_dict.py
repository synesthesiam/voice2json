#!/usr/bin/env python3
import logging

logger = logging.getLogger("vocab_dict")

import os
import re
import sys
from pathlib import Path
from typing import Iterable, Optional, List, Dict, Callable, TextIO


def make_dict(
    vocab_path: Path,
    dictionary_paths: Iterable[Path],
    dictionary_file: TextIO,
    unknown_path: Optional[Path] = None,
    upper: bool = False,
    lower: bool = False,
    no_number: bool = False,
) -> List[str]:
    transform = lambda w: w
    if upper:
        transform = lambda w: w.upper()
        logger.debug("Forcing upper-case")
    elif lower:
        transform = lambda w: w.lower()
        logger.debug("Forcing lower-case")

    # Read dictionaries
    word_dict: Dict[str, List[str]] = {}
    for dict_path in dictionary_paths:
        if os.path.exists(dict_path):
            logger.debug(f"Loading dictionary from {dict_path}")
            with open(dict_path, "r") as dict_file:
                read_dict(dict_file, word_dict, transform)

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

    # Write output dictionary
    unknown_words: List[str] = []
    for word in sorted(words_needed):
        if not word in word_dict:
            unknown_words.append(word)
            continue

        for i, pronounce in enumerate(word_dict[word]):
            if (i < 1) or no_number:
                print(word, pronounce, file=dictionary_file)
            else:
                print("%s(%s)" % (word, i + 1), pronounce, file=dictionary_file)

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


# -----------------------------------------------------------------------------


def read_dict(
    dict_file: Iterable[str],
    word_dict: Optional[Dict[str, List[str]]] = None,
    transform: Optional[Callable[[str], str]] = None,
) -> Dict[str, List[str]]:
    """
    Loads a CMU word dictionary, optionally into an existing Python dictionary.
    """
    if word_dict is None:
        word_dict = {}

    for line in dict_file:
        line = line.strip()
        if len(line) == 0:
            continue

        try:
            # Use explicit whitespace (avoid 0xA0)
            word, pronounce = re.split(r"[ \t]+", line, maxsplit=1)

            idx = word.find("(")
            if idx > 0:
                word = word[:idx]

            if transform:
                word = transform(word)

            pronounce = pronounce.strip()
            if word in word_dict:
                word_dict[word].append(pronounce)
            else:
                word_dict[word] = [pronounce]
        except Exception as e:
            logger.warning(f"read_dict: {e}")

    return word_dict
