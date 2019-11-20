import re
from typing import List, Mapping, Any, Iterable, Optional
from collections import deque

import pywrapfst as fst
import networkx as nx

from voice2json.intent.const import (
    Recognition,
    RecognitionResult,
    Intent,
    Entity,
    TagInfo,
)


# See:
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


def fstprintall(
    in_fst: fst.Fst, exclude_meta: bool = True, eps: str = "<eps>"
) -> Iterable[List[str]]:
    """Generate all possible sentences from an FST."""
    output_symbols = in_fst.output_symbols()
    out_eps = output_symbols.find(eps)
    zero_weight = fst.Weight.Zero(in_fst.weight_type())

    state_queue = deque()
    state_queue.append((in_fst.start(), []))

    while len(state_queue) > 0:
        state, sentence = state_queue.popleft()

        if in_fst.final(state) != zero_weight:
            yield sentence

        for arc in in_fst.arcs(state):
            arc_sentence = list(sentence)
            if arc.olabel != out_eps:
                out_symbol = output_symbols.find(arc.olabel).decode()
                if exclude_meta and out_symbol.startswith("__"):
                    pass  # skip __label__, etc.
                else:
                    arc_sentence.append(out_symbol)

            state_queue.append((arc.nextstate, arc_sentence))


def symbols2intent(
    symbols: List[str], eps: str = "<eps>", replace_tags: bool = True
) -> Recognition:
    """Transform FST symbols into an intent and recognition."""
    intent: Optional[Intent] = None
    tag_stack: List[TagInfo] = []
    out_symbols: List[str] = []
    raw_symbols: List[str] = []
    out_index: int = 0
    raw_out_index: int = 0

    # Find intent label
    resume_index = 0
    for i, sym in enumerate(symbols):
        if sym.startswith("__label__"):
            # Intent label
            intent = Intent(sym[9:])
            resume_index = i + 1
            break

    # Process remaining symbols
    for sym in symbols[resume_index:]:
        if sym == eps:
            continue

        if sym.startswith("__begin__"):
            # Begin tag
            tag_stack.append(
                TagInfo(
                    tag=sym[9:], start_index=out_index, raw_start_index=raw_out_index
                )
            )
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
            intent.entities.append(
                Entity(
                    entity=tag,
                    value=tag_value,
                    raw_value=raw_value,
                    start=tag_start_index,
                    raw_start=tag_raw_start_index,
                    end=out_index - 1,
                    raw_end=raw_out_index - 1,
                )
            )
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

    if intent is None:
        return Recognition(result=RecognitionResult.FAILURE)

    return Recognition(
        result=RecognitionResult.SUCCESS,
        intent=intent,
        text=" ".join(out_symbols),
        raw_text=" ".join(raw_symbols),
        tokens=out_symbols,
        raw_tokens=raw_symbols,
    )


def fst_to_graph(the_fst: fst.Fst) -> nx.MultiDiGraph:
    """Converts a finite state transducer to a directed graph."""
    zero_weight = fst.Weight.Zero(the_fst.weight_type())
    in_symbols = the_fst.input_symbols()
    out_symbols = the_fst.output_symbols()

    g = nx.MultiDiGraph()

    # Add nodes
    for state in the_fst.states():
        # Mark final states
        is_final = the_fst.final(state) != zero_weight
        g.add_node(state, final=is_final, start=False)

        # Add edges
        for arc in the_fst.arcs(state):
            in_label = in_symbols.find(arc.ilabel).decode()
            out_label = out_symbols.find(arc.olabel).decode()

            g.add_edge(state, arc.nextstate, in_label=in_label, out_label=out_label)

    # Mark start state
    g.add_node(the_fst.start(), start=True)

    return g
