#!/usr/bin/env python3
import logging

logger = logging.getLogger("fsticuffs")

import re
import time
from typing import Optional, Dict, Any, Set, List, Tuple

import pywrapfst as fst
import networkx as nx

from voice2json.train.jsgf2fst import fstaccept, symbols2intent

# -------------------------------------------------------------------------------------------------


def recognize(
    intent_fst: fst.Fst, text: str, known_tokens: Optional[Set[str]] = None
) -> Dict[str, Any]:
    start_time = time.time()
    tokens = re.split("\s+", text)

    if known_tokens:
        # Filter tokens
        tokens = [t for t in tokens if t in known_tokens]

    # Only run acceptor if there are any tokens
    if len(tokens) > 0:
        intents = fstaccept(intent_fst, tokens)
    else:
        intents = []

    logger.debug(f"Recognized {len(intents)} intent(s)")

    # Use first intent
    if len(intents) > 0:
        intent = intents[0]

        # Add slots
        intent["slots"] = {}
        for ev in intent["entities"]:
            intent["slots"][ev["entity"]] = ev["value"]

        # Add alternative intents
        intent["intents"] = []
        for other_intent in intents[1:]:
            intent["intents"].append(other_intent)
    else:
        intent = empty_intent()
        intent["text"] = text

    # Record recognition time
    intent["recognize_seconds"] = time.time() - start_time

    return intent


# -------------------------------------------------------------------------------------------------


def recognize_fuzzy(
    intent_graph: nx.digraph.Graph,
    text: str,
    known_tokens: Optional[Set[str]] = None,
    stop_words: Set[str] = set(),
    eps: str = "<eps>",
) -> Dict[str, Any]:
    start_time = time.time()
    tokens = re.split("\s+", text)

    if known_tokens:
        # Filter tokens
        tokens = [t for t in tokens if t in known_tokens]

    # Only run search if there are any tokens
    intents = []
    if len(tokens) > 0:
        intent_symbols_and_costs = _get_symbols_and_costs(
            intent_graph, tokens, stop_words=stop_words, eps=eps
        )
        for intent_name, (symbols, cost) in intent_symbols_and_costs.items():
            intent = symbols2intent(symbols, eps=eps)
            intent["intent"]["confidence"] = (len(tokens) - cost) / len(tokens)
            intents.append(intent)

        intents = sorted(intents, key=lambda i: i["intent"]["confidence"], reverse=True)

    logger.debug(f"Recognized {len(intents)} intent(s)")

    # Use first intent
    if len(intents) > 0:
        intent = intents[0]

        # Add slots
        intent["slots"] = {}
        for ev in intent["entities"]:
            intent["slots"][ev["entity"]] = ev["value"]

        # Add alternative intents
        intent["intents"] = []
        for other_intent in intents[1:]:
            intent["intents"].append(other_intent)
    else:
        intent = empty_intent()
        intent["text"] = text

    # Record recognition time
    intent["recognize_seconds"] = time.time() - start_time

    return intent


def _get_symbols_and_costs(
    intent_graph: nx.MultiDiGraph,
    tokens: List[str],
    stop_words: Set[str] = set(),
    eps: str = "<eps>",
) -> Dict[str, Tuple[List[str], int]]:
    # node -> attrs
    n_data = intent_graph.nodes(data=True)

    # start state
    start_node = [n for n, data in n_data if data["start"]][0]

    # intent -> (symbols, cost)
    intent_symbols_and_costs = {}

    # Lowest cost so far
    best_cost = len(n_data)

    # (node, in_tokens, out_tokens, cost, intent_name)
    q = [(start_node, tokens, [], 0, None)]

    # BFS it up
    while len(q) > 0:
        q_node, q_in_tokens, q_out_tokens, q_cost, q_intent = q.pop()

        # Update best intent cost on final state.
        # Don't bother reporting intents that failed to consume any tokens.
        if (n_data[q_node]["final"]) and (q_cost < len(tokens)):
            best_intent_cost = intent_symbols_and_costs.get(q_intent, (None, None))[1]
            final_cost = q_cost + len(q_in_tokens)  # remaning tokens count against

            if (best_intent_cost is None) or (final_cost < best_intent_cost):
                intent_symbols_and_costs[q_intent] = [q_out_tokens, final_cost]

            if final_cost < best_cost:
                best_cost = final_cost

        if q_cost > best_cost:
            continue

        # Process child edges
        for next_node, edges in intent_graph[q_node].items():
            for edge_idx, edge_data in edges.items():
                in_label = edge_data["in_label"]
                out_label = edge_data["out_label"]
                next_in_tokens = q_in_tokens[:]
                next_out_tokens = q_out_tokens[:]
                next_cost = q_cost
                next_intent = q_intent

                if out_label.startswith("__label__"):
                    next_intent = out_label[9:]

                if in_label in stop_words:
                    # Only consume token if it matches (no penalty if not)
                    if (len(next_in_tokens) > 0) and (in_label == next_in_tokens[0]):
                        next_in_tokens.pop(0)

                    if out_label != eps:
                        next_out_tokens.append(out_label)
                elif in_label != eps:
                    # Consume non-matching tokens and increase cost
                    while (len(next_in_tokens) > 0) and (in_label != next_in_tokens[0]):
                        next_in_tokens.pop(0)
                        next_cost += 1

                    if len(next_in_tokens) > 0:
                        # Consume matching token
                        next_in_tokens.pop(0)

                        if out_label != eps:
                            next_out_tokens.append(out_label)
                    else:
                        # No matching token
                        continue
                else:
                    # Consume epsilon
                    if out_label != eps:
                        next_out_tokens.append(out_label)

                q.append(
                    [next_node, next_in_tokens, next_out_tokens, next_cost, next_intent]
                )

    return intent_symbols_and_costs


# -------------------------------------------------------------------------------------------------


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


# -------------------------------------------------------------------------------------------------


def empty_intent() -> Dict[str, Any]:
    return {
        "text": "",
        "intent": {"name": "", "confidence": 0},
        "entities": [],
        "intents": [],
        "slots": {},
        "recognize_seconds": 0.0,
    }
