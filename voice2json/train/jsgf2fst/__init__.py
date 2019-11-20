#!/usr/bin/env python3
import os
import sys
import argparse
import re
import io
import subprocess
import tempfile
import shutil
import itertools
import collections
from collections import defaultdict, deque
import logging
from pathlib import Path
from typing import Set, List, Dict, Union, Any, Tuple, Optional

import pywrapfst as fst
import networkx as nx

from .FSTListener import FSTListener
from .DependencyListener import DependencyListener

from voice2json.utils import numbers_to_words

logger = logging.getLogger("jsgf2fst")

# -----------------------------------------------------------------------------

JSGF_RESERVED = re.compile(r"[;=,*+()<>{}\[]]")

# -----------------------------------------------------------------------------


def get_grammar_dependencies(grammar: str) -> DependencyListener:
    """Parses JSGF grammar and creates a dependency graph."""
    listener = DependencyListener(grammar)
    listener.walk()

    return listener


def grammar_to_fsts(
    grammar: str,
    replace_fsts: Dict[str, fst.Fst] = {},
    eps: str = "<eps>",
    lower: bool = False,
    upper: bool = False,
) -> FSTListener:
    """Transforms JSGF grammar into an FST."""

    # Casing transformation
    transform = lambda w: w
    if upper:
        transform = lambda w: w.upper()
        logger.debug("Forcing upper-case")
    elif lower:
        transform = lambda w: w.lower()
        logger.debug("Forcing lower-case")

    listener = FSTListener(grammar, eps=eps, transform=transform)
    listener.walk()

    # Check for replacements
    grammar_name = listener.grammar_name
    replace_indices: Dict[int, str] = {}

    # Gather all __replace__ references
    output_symbols = listener.output_symbols
    for i in range(output_symbols.num_symbols()):
        symbol = output_symbols.find(i).decode()
        if symbol.startswith("__replace__"):
            replace_indices[i] = symbol[11:]

    # Handle __replace__
    graph = listener.graph
    postorder = nx.algorithms.traversal.dfs_postorder_nodes(
        listener.graph, listener.grammar_name
    )

    for node in postorder:
        node_type = graph.nodes[node]["type"]

        # Only consider local rules as targets for replacement
        if node_type != "local rule":
            continue

        rule_name, rule_fst = node, listener.fsts[node]

        # Check arcs for replacements
        replace_names: Dict[str, int] = {}
        for state in rule_fst.states():
            for arc in rule_fst.arcs(state):
                replace_name = replace_indices.get(arc.olabel)
                if replace_name is not None:
                    replace_names[replace_name] = arc.olabel

        # Do FST replacements
        if len(replace_names) > 0:
            replacements: Dict[int, fst.Fst] = {}
            for replace_name, replace_index in replace_names.items():
                # Look in replacement and local FST lists
                replace_fst = replace_fsts.get(replace_name) or listener.fsts.get(
                    replace_name
                )
                if replace_fst is None:
                    logger.warning(
                        f"Missing {replace_name} in replacement FSTs for {grammar_name}"
                    )
                    continue

                replacements[replace_index] = replace_fst

            logger.debug("Replacing %s in %s", list(replace_names.keys()), rule_name)
            listener.fsts[rule_name] = _replace_fsts(rule_fst, replacements, eps=eps)

    # Overwrite grammar_fst
    main_rule = listener.grammar_name + "." + listener.grammar_name
    listener.grammar_fst = listener.fsts[main_rule]

    return listener


def slots_to_fsts(
    slots_dir: Path,
    slot_names: Optional[Set[str]] = None,
    eps: str = "<eps>",
    upper: bool = False,
    lower: bool = False,
    replace_numbers: bool = False,
    language: Optional[str] = None,
) -> Dict[str, fst.Fst]:
    """Transform slot values into FSTs."""
    slot_fsts: Dict[str, fst.Fst] = {}

    # Casing transformation
    transform = lambda w: w
    if upper:
        transform = lambda w: w.upper()
        logger.debug("Forcing upper-case")
    elif lower:
        transform = lambda w: w.lower()
        logger.debug("Forcing lower-case")

    if replace_numbers:
        # Replace numbers with words
        old_transform = transform
        transform = lambda w: numbers_to_words(
            old_transform(w), language=language, add_substitution=True
        )

    # Process slots
    for slot_path in slots_dir.glob("*"):
        # Skip directories
        if not slot_path.is_file():
            continue

        slot_name = slot_path.name

        # Skip slots not in include list
        if (slot_names is not None) and (slot_name not in slot_names):
            continue

        slot_fst = fst.Fst()
        weight_one = fst.Weight.One(slot_fst.weight_type())
        slot_start = slot_fst.add_state()
        slot_fst.set_start(slot_start)

        slot_end = slot_fst.add_state()
        slot_fst.set_final(slot_end)

        input_symbols = fst.SymbolTable()
        in_eps = input_symbols.add_symbol(eps)

        output_symbols = fst.SymbolTable()
        out_eps = output_symbols.add_symbol(eps)

        replacements: Dict[str, fst.Fst] = {}

        with open(slot_path, "r") as slot_file:
            # Process each line independently to avoid recursion limit
            for line in slot_file:
                line = line.strip()
                if len(line) == 0:
                    continue

                # Handle casing/numbers
                line = transform(line)

                replace_symbol = f"__replace__{len(replacements)}"
                out_replace = output_symbols.add_symbol(replace_symbol)

                # Convert to JSGF grammar
                with io.StringIO() as grammar_file:
                    print("#JSGF v1.0;", file=grammar_file)
                    print(f"grammar {slot_name};", file=grammar_file)
                    print(f"public <{slot_name}> = ({line});", file=grammar_file)

                    line_grammar = grammar_file.getvalue()
                    line_fst = grammar_to_fsts(line_grammar).grammar_fst

                    slot_fst.add_arc(
                        slot_start, fst.Arc(in_eps, out_replace, weight_one, slot_end)
                    )

                    replacements[out_replace] = line_fst

        # ---------------------------------------------------------------------

        # Fix symbol tables
        slot_fst.set_input_symbols(input_symbols)
        slot_fst.set_output_symbols(output_symbols)

        # Replace slot values
        slot_fsts["$" + slot_name] = _replace_fsts(slot_fst, replacements)

    return slot_fsts


# -----------------------------------------------------------------------------


def make_intent_fst(grammar_fsts: Dict[str, fst.Fst], eps: str = "<eps>") -> fst.Fst:
    """Merges grammar FSTs created with grammar_to_fsts into a single acceptor FST."""
    input_symbols = fst.SymbolTable()
    output_symbols = fst.SymbolTable()

    in_eps: int = input_symbols.add_symbol(eps)
    out_eps: int = output_symbols.add_symbol(eps)

    intent_fst = fst.Fst()
    weight_one = fst.Weight.One(intent_fst.weight_type())

    # Create start/final states
    start_state = intent_fst.add_state()
    intent_fst.set_start(start_state)

    final_state = intent_fst.add_state()
    intent_fst.set_final(final_state)

    replacements: Dict[int, fst.Fst] = {}

    for intent, grammar_fst in grammar_fsts.items():
        intent_label = f"__label__{intent}"
        out_label = output_symbols.add_symbol(intent_label)

        # --[__label__INTENT]-->
        intent_start = intent_fst.add_state()
        intent_fst.add_arc(
            start_state, fst.Arc(in_eps, out_label, weight_one, intent_start)
        )

        # --[__replace__INTENT]-->
        intent_end = intent_fst.add_state()
        replace_symbol = f"__replace__{intent}"
        out_replace = output_symbols.add_symbol(replace_symbol)
        intent_fst.add_arc(
            intent_start, fst.Arc(in_eps, out_replace, weight_one, intent_end)
        )

        # --[eps]-->
        intent_fst.add_arc(
            intent_end, fst.Arc(in_eps, out_eps, weight_one, final_state)
        )

        replacements[out_replace] = grammar_fst

    # Fix symbol tables
    intent_fst.set_input_symbols(input_symbols)
    intent_fst.set_output_symbols(output_symbols)

    # Do replacements

    return _replace_fsts(intent_fst, replacements, eps=eps)


# -----------------------------------------------------------------------------


def _replace_fsts(
    outer_fst: fst.Fst, replacements: Dict[int, fst.Fst], eps="<eps>"
) -> fst.Fst:
    input_symbol_map: Dict[Union[int, Tuple[int, int]], int] = {}
    output_symbol_map: Dict[Union[int, Tuple[int, int]], int] = {}
    state_map: Dict[Union[int, Tuple[int, int]], int] = {}

    # Create new FST
    new_fst = fst.Fst()
    new_input_symbols = fst.SymbolTable()
    new_output_symbols = fst.SymbolTable()

    weight_one = fst.Weight.One(new_fst.weight_type())
    weight_zero = fst.Weight.Zero(new_fst.weight_type())
    weight_final = fst.Weight.Zero(outer_fst.weight_type())

    # Copy symbols
    outer_input_symbols = outer_fst.input_symbols()
    for i in range(outer_input_symbols.num_symbols()):
        key = outer_input_symbols.get_nth_key(i)
        input_symbol_map[key] = new_input_symbols.add_symbol(
            outer_input_symbols.find(key)
        )

    outer_output_symbols = outer_fst.output_symbols()
    for i in range(outer_output_symbols.num_symbols()):
        key = outer_output_symbols.get_nth_key(i)
        output_symbol_map[key] = new_output_symbols.add_symbol(
            outer_output_symbols.find(key)
        )

    in_eps = new_input_symbols.add_symbol(eps)
    out_eps = new_output_symbols.add_symbol(eps)

    # Copy states
    for outer_state in outer_fst.states():
        new_state = new_fst.add_state()
        state_map[outer_state] = new_state

        if outer_fst.final(outer_state) != weight_final:
            new_fst.set_final(new_state)

    # Set start state
    new_fst.set_start(state_map[outer_fst.start()])

    # Copy arcs
    for outer_state in outer_fst.states():
        new_state = state_map[outer_state]
        for outer_arc in outer_fst.arcs(outer_state):
            next_state = state_map[outer_arc.nextstate]
            replace_fst = replacements.get(outer_arc.olabel)

            if replace_fst is not None:
                # Replace in-line
                r = outer_arc.olabel
                replace_final = fst.Weight.Zero(replace_fst.weight_type())
                replace_input_symbols = replace_fst.input_symbols()
                replace_output_symbols = replace_fst.output_symbols()

                # Copy states
                for replace_state in replace_fst.states():
                    state_map[(r, replace_state)] = new_fst.add_state()

                    # Create final arc to next state
                    if replace_fst.final(replace_state) != replace_final:
                        new_fst.add_arc(
                            state_map[(r, replace_state)],
                            fst.Arc(in_eps, out_eps, weight_one, next_state),
                        )

                # Copy arcs
                for replace_state in replace_fst.states():
                    for replace_arc in replace_fst.arcs(replace_state):
                        new_fst.add_arc(
                            state_map[(r, replace_state)],
                            fst.Arc(
                                new_input_symbols.add_symbol(
                                    replace_input_symbols.find(replace_arc.ilabel)
                                ),
                                new_output_symbols.add_symbol(
                                    replace_output_symbols.find(replace_arc.olabel)
                                ),
                                weight_one,
                                state_map[(r, replace_arc.nextstate)],
                            ),
                        )

                # Create arc into start state
                new_fst.add_arc(
                    new_state,
                    fst.Arc(
                        in_eps, out_eps, weight_one, state_map[(r, replace_fst.start())]
                    ),
                )
            else:
                # Copy arc as-is
                new_fst.add_arc(
                    new_state,
                    fst.Arc(
                        input_symbol_map[outer_arc.ilabel],
                        output_symbol_map[outer_arc.olabel],
                        weight_one,
                        next_state,
                    ),
                )

    # Fix symbol tables
    new_fst.set_input_symbols(new_input_symbols)
    new_fst.set_output_symbols(new_output_symbols)

    return new_fst
