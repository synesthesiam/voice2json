#!/usr/bin/env python3
import logging

logger = logging.getLogger("ini_jsgf")

import os
import re
import sys
import configparser
from typing import TextIO, List, Iterable, Optional, Dict
from pathlib import Path


def make_grammars(
    ini_file: TextIO,
    grammar_dir: Path,
    whitelist: Optional[Iterable[str]] = None,
    no_overwrite: bool = False,
) -> Dict[str, Path]:
    # Create output directory
    grammar_dir.mkdir(parents=True, exist_ok=True)

    # Create ini parser
    config = configparser.ConfigParser(
        allow_no_value=True, strict=False, delimiters=["="]
    )

    config.optionxform = lambda x: str(x)  # case sensitive
    config.read_file(ini_file)

    logger.debug("Loaded ini file")

    # Process configuration sections
    grammar_rules = {}

    for sec_name in config.sections():
        if (whitelist is not None) and (sec_name not in whitelist):
            logger.debug("Skipping %s (not in whitelist)", sec_name)
            continue

        sentences: List[str] = []
        rules: List[str] = []
        for k, v in config[sec_name].items():
            if v is None:
                # Collect non-valued keys as sentences
                sentences.append("({0})".format(k.strip()))
            else:
                # Collect key/value pairs as JSGF rules
                rule = "<{0}> = ({1});".format(k, v)
                rules.append(rule)

        if len(sentences) > 0:
            # Combine all sentences into one big rule (same name as section)
            sentences_rule = "public <{0}> = ({1});".format(
                sec_name, " | ".join(sentences)
            )
            rules.insert(0, sentences_rule)

        grammar_rules[sec_name] = rules

    # Write JSGF grammars
    grammar_paths: Dict[str, Path] = {}
    for name, rules in grammar_rules.items():
        grammar_path = grammar_dir / f"{name}.gram"
        grammar_paths[name] = grammar_path

        if grammar_path.exists() and no_overwrite:
            logger.debug("Skipping %s", grammar_path)
            continue

        # Only overwrite grammar file if it contains rules or doesn't yet exist
        if len(rules) > 0:
            with open(grammar_path, "w") as grammar_file:
                # JSGF header
                print(f"#JSGF V1.0;", file=grammar_file)
                print("grammar {0};".format(name), file=grammar_file)
                print("", file=grammar_file)

                # Grammar rules
                for rule in rules:
                    # Handle special case where sentence starts with ini
                    # reserved character '['. In this case, use '\[' to pass
                    # it through to the JSGF grammar, where we deal with it
                    # here.
                    rule = re.sub(r"\\\[", "[", rule)
                    print(rule, file=grammar_file)

            logger.debug("Wrote %s (%s rule(s))", grammar_path, len(rules))
        else:
            logger.debug("No rules for %s", grammar_path)

    return grammar_paths
