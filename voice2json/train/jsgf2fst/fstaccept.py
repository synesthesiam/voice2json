#!/usr/bin/env python3
import os
import sys
import argparse
import re
import json
import logging
from typing import Dict, Any, List, Optional, TextIO, Mapping, Union, Iterable
from collections import deque, defaultdict, Counter

import pywrapfst as fst
import networkx as nx

logger = logging.getLogger("fstaccept")


def fstaccept(
    in_fst: fst.Fst,
    sentence: Union[str, List[str]],
    intent_name: Optional[str] = None,
    replace_tags: bool = True,
) -> List[Dict[str, Any]]:
    """Recognizes an intent from a sentence using a FST."""

    if isinstance(sentence, str):
        # Assume lower case, white-space separated tokens
        sentence = sentence.strip().lower()
        words = re.split(r"\s+", sentence)
    else:
        words = sentence

    intents = []

    try:
        out_fst = apply_fst(words, in_fst)

        # Get output symbols
        out_sentences = fstprintall(out_fst, exclude_meta=False)
        for out_sentence in out_sentences:
            out_intent_name = intent_name
            intent = symbols2intent(
                out_sentence, intent_name=out_intent_name, replace_tags=replace_tags
            )
            intent["intent"]["confidence"] /= len(out_sentences)
            intents.append(intent)
    except:
        # Error, assign blank result
        logger.exception(sentence)

    return intents


# -----------------------------------------------------------------------------


class TagInfo:
    def __init__(
        self, tag, start_index, raw_start_index, symbols=None, raw_symbols=None
    ):
        self.tag = tag
        self.start_index = start_index
        self.raw_start_index = raw_start_index
        self.symbols = symbols or []
        self.raw_symbols = raw_symbols or []


def symbols2intent(
    symbols: List[str],
    eps: str = "<eps>",
    intent: Optional[Dict[str, Any]] = None,
    intent_name: Optional[str] = None,
    replace_tags: bool = True,
) -> Dict[str, Any]:
    intent = intent or empty_intent()
    tag_stack: List[TagInfo] = []
    out_symbols: List[str] = []
    raw_symbols: List[str] = []
    out_index = 0
    raw_out_index = 0

    for sym in symbols:
        if sym == eps:
            continue

        if sym.startswith("__begin__"):
            # Begin tag
            tag_stack.append(TagInfo(sym[9:], out_index, raw_out_index))
        elif sym.startswith("__end__"):
            assert len(tag_stack) > 0, f"Unbalanced tags. Got {sym}."

            # End tag
            tag_info = tag_stack.pop()
            tag, tag_symbols, tag_raw_symbols, tag_start_index, tag_raw_start_index = (
                tag_info.tag,
                tag_info.symbols,
                tag_info.raw_symbols,
                tag_info.start_index,
                tag_info.raw_start_index,
            )
            assert tag == sym[7:], f"Mismatched tags: {tag} {sym[7:]}"

            raw_value = " ".join(tag_raw_symbols)
            raw_symbols.extend(tag_raw_symbols)

            if replace_tags and (":" in tag):
                # Use replacement string in the tag
                tag, tag_value = tag.split(":", maxsplit=1)
                out_symbols.extend(re.split(r"\s+", tag_value))
            else:
                # Use text between begin/end
                tag_value = " ".join(tag_symbols)
                out_symbols.extend(tag_symbols)

            out_index += len(tag_value) + 1  # space
            raw_out_index += len(raw_value) + 1  # space
            intent["entities"].append(
                {
                    "entity": tag,
                    "value": tag_value,
                    "raw_value": raw_value,
                    "start": tag_start_index,
                    "raw_start": tag_raw_start_index,
                    "end": out_index - 1,
                    "raw_end": raw_out_index - 1,
                }
            )
        elif sym.startswith("__label__"):
            # Intent label
            if intent_name is None:
                intent_name = sym[9:]
        elif len(tag_stack) > 0:
            # Inside tag
            for tag_info in tag_stack:
                if ":" in sym:
                    # Use replacement text
                    in_sym, out_sym = sym.split(":", maxsplit=1)

                    if len(in_sym.strip()) > 0:
                        tag_info.raw_symbols.append(in_sym)

                    if len(out_sym.strip()) > 0:
                        # Ignore empty output symbols
                        tag_info.symbols.append(out_sym)
                else:
                    # Use original symbol
                    tag_info.raw_symbols.append(sym)
                    tag_info.symbols.append(sym)
        else:
            # Outside tag
            if ":" in sym:
                # Use replacement symbol
                in_sym, out_sym = sym.split(":", maxsplit=1)

                if len(in_sym.strip()) > 0:
                    raw_symbols.append(in_sym)

                if len(out_sym.strip()) > 0:
                    # Ignore empty output symbols
                    out_symbols.append(out_sym)
                    out_index += len(out_sym) + 1  # space
                    raw_out_index += len(out_sym) + 1  # space
            else:
                # Use original symbol
                raw_symbols.append(sym)
                out_symbols.append(sym)
                out_index += len(sym) + 1  # space
                raw_out_index += len(sym) + 1  # space

    intent["text"] = " ".join(out_symbols)
    intent["raw_text"] = " ".join(raw_symbols)
    intent["tokens"] = out_symbols
    intent["raw_tokens"] = raw_symbols

    if len(out_symbols) > 0:
        intent["intent"]["name"] = intent_name or ""
        intent["intent"]["confidence"] = 1

    return intent


# -----------------------------------------------------------------------------


def fstprintall(
    in_fst: fst.Fst,
    out_file: Optional[TextIO] = None,
    exclude_meta: bool = True,
    eps: str = "<eps>",
) -> List[List[str]]:
    sentences = []
    output_symbols = in_fst.output_symbols()
    out_eps = output_symbols.find(eps)
    zero_weight = fst.Weight.Zero(in_fst.weight_type())
    visited_states = set()

    state_queue = deque()
    state_queue.append((in_fst.start(), []))

    while len(state_queue) > 0:
        state, sentence = state_queue.popleft()
        if state in visited_states:
            continue

        visited_states.add(state)

        if in_fst.final(state) != zero_weight:
            if out_file:
                print(" ".join(sentence), file=out_file)
            else:
                sentences.append(sentence)

        for arc in in_fst.arcs(state):
            arc_sentence = list(sentence)
            if arc.olabel != out_eps:
                out_symbol = output_symbols.find(arc.olabel).decode()
                if exclude_meta and out_symbol.startswith("__"):
                    pass  # skip __label__, etc.
                else:
                    arc_sentence.append(out_symbol)

            state_queue.append((arc.nextstate, arc_sentence))

    return sentences


# -----------------------------------------------------------------------------


def longest_path(the_fst: fst.Fst, eps: str = "<eps>") -> fst.Fst:
    output_symbols = the_fst.output_symbols()
    out_eps = output_symbols.find(eps)
    visited_states: Set[int] = set()
    best_path = []
    state_queue = deque()
    state_queue.append((the_fst.start(), []))

    # Determine longest path
    while len(state_queue) > 0:
        state, path = state_queue.popleft()
        if state in visited_states:
            continue

        visited_states.add(state)

        if len(path) > len(best_path):
            best_path = path

        for arc in the_fst.arcs(state):
            next_path = list(path)
            next_path.append(arc.olabel)
            state_queue.append((arc.nextstate, next_path))

    # Create FST with longest path
    path_fst = fst.Fst()

    input_symbols = fst.SymbolTable()
    input_symbols.add_symbol(eps)
    path_fst.set_output_symbols(output_symbols)
    weight_one = fst.Weight.One(path_fst.weight_type())

    state = path_fst.add_state()
    path_fst.set_start(state)

    for olabel in best_path:
        osym = output_symbols.find(olabel).decode()
        next_state = path_fst.add_state()
        path_fst.add_arc(
            state,
            fst.Arc(input_symbols.add_symbol(osym), olabel, weight_one, next_state),
        )
        state = next_state

    path_fst.set_final(state)
    path_fst.set_input_symbols(input_symbols)

    return path_fst


# -----------------------------------------------------------------------------


def filter_words(words: Iterable[str], the_fst: fst.Fst) -> List[str]:
    input_symbols = the_fst.input_symbols()
    return [w for w in words if input_symbols.find(w) >= 0]


# -----------------------------------------------------------------------------


def make_slot_acceptor(intent_fst: fst.Fst, eps: str = "<eps>") -> fst.Fst:
    in_eps = intent_fst.input_symbols().find(eps)
    out_eps = intent_fst.output_symbols().find(eps)
    slot_fst = fst.Fst()

    # Copy symbol tables
    all_symbols = fst.SymbolTable()
    meta_keys = set()

    for table in [intent_fst.input_symbols(), intent_fst.output_symbols()]:
        for i in range(table.num_symbols()):
            key = table.get_nth_key(i)
            sym = table.find(key).decode()
            all_key = all_symbols.add_symbol(sym)
            if sym.startswith("__"):
                meta_keys.add(all_key)

    weight_one = fst.Weight.One(slot_fst.weight_type())
    weight_zero = fst.Weight.Zero(slot_fst.weight_type())

    # States that will be set to final
    final_states: Set[int] = set()

    # States that already have all-word loops
    loop_states: Set[int] = set()

    all_eps = all_symbols.find(eps)

    # Add self transitions to a state for all input words (besides <eps>)
    def add_loop_state(state):
        for sym_idx in range(all_symbols.num_symbols()):
            all_key = all_symbols.get_nth_key(sym_idx)
            if (all_key != all_eps) and (all_key not in meta_keys):
                slot_fst.add_arc(state, fst.Arc(all_key, all_key, weight_one, state))

    slot_fst.set_start(slot_fst.add_state())

    # Queue of (intent state, acceptor state, copy count)
    state_queue = deque()
    state_queue.append((intent_fst.start(), slot_fst.start(), 0))

    # BFS
    while len(state_queue) > 0:
        intent_state, slot_state, do_copy = state_queue.popleft()
        final_states.add(slot_state)
        for intent_arc in intent_fst.arcs(intent_state):
            out_symbol = intent_fst.output_symbols().find(intent_arc.olabel).decode()
            all_key = all_symbols.find(out_symbol)

            if out_symbol.startswith("__label__"):
                # Create corresponding __label__ arc
                next_state = slot_fst.add_state()
                slot_fst.add_arc(
                    slot_state, fst.Arc(all_key, all_key, weight_one, next_state)
                )

                # Must create a loop here for intents with no slots
                add_loop_state(next_state)
                loop_states.add(slot_state)
            else:
                # Non-label arc
                if out_symbol.startswith("__begin__"):
                    # States/arcs will be copied until __end__ is reached
                    do_copy += 1

                    # Add loop transitions to soak up non-tag words
                    if not slot_state in loop_states:
                        add_loop_state(slot_state)
                        loop_states.add(slot_state)

                if (do_copy > 0) and (
                    (intent_arc.ilabel != in_eps) or (intent_arc.olabel != out_eps)
                ):
                    # Copy state/arc
                    in_symbol = (
                        intent_fst.input_symbols().find(intent_arc.ilabel).decode()
                    )
                    next_state = slot_fst.add_state()
                    slot_fst.add_arc(
                        slot_state,
                        fst.Arc(
                            all_symbols.find(in_symbol), all_key, weight_one, next_state
                        ),
                    )
                    final_states.discard(slot_state)
                else:
                    next_state = slot_state

                if out_symbol.startswith("__end__"):
                    # Stop copying after this state until next __begin__
                    do_copy -= 1

            next_info = (intent_arc.nextstate, next_state, do_copy)
            state_queue.append(next_info)

    # Mark all dangling states as final (excluding start)
    for state in final_states:
        if state != slot_fst.start():
            slot_fst.set_final(state)

    # Fix symbol tables
    slot_fst.set_input_symbols(all_symbols)
    slot_fst.set_output_symbols(all_symbols)

    return slot_fst


# -----------------------------------------------------------------------------

# From:
# https://stackoverflow.com/questions/9390536/how-do-you-even-give-an-openfst-made-fst-input-where-does-the-output-go


def linear_fst(
    elements: List[str],
    automata_op: fst.Fst,
    keep_isymbols: bool = True,
    **kwargs: Mapping[Any, Any],
) -> fst.Fst:
    """Produce a linear automata."""
    assert len(elements) > 0, "No elements"
    compiler = fst.Compiler(
        isymbols=automata_op.input_symbols().copy(),
        acceptor=keep_isymbols,
        keep_isymbols=keep_isymbols,
        **kwargs,
    )

    num_elements = 0
    for i, el in enumerate(elements):
        print("{} {} {}".format(i, i + 1, el), file=compiler)
        num_elements += 1

    print(str(num_elements), file=compiler)

    return compiler.compile()


def apply_fst(
    elements: List[str],
    automata_op: fst.Fst,
    is_project: bool = True,
    **kwargs: Mapping[Any, Any],
) -> fst.Fst:
    """Compose a linear automata generated from `elements` with `automata_op`.

    Args:
        elements (list): ordered list of edge symbols for a linear automata.
        automata_op (Fst): automata that will be applied.
        is_project (bool, optional): whether to keep only the output labels.
        kwargs:
            Additional arguments to the compiler of the linear automata .
    """
    linear_automata = linear_fst(elements, automata_op, keep_isymbols=True, **kwargs)
    out = fst.compose(linear_automata, automata_op)
    if is_project:
        out.project(project_output=True)
    return out


# -----------------------------------------------------------------------------


def empty_intent() -> Dict[str, Any]:
    return {"text": "", "intent": {"name": "", "confidence": 0}, "entities": []}
