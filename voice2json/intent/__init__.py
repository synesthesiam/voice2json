"""Text to intent recognizers."""
import logging
import time
from typing import List, Dict, Set, Optional, Tuple

import pywrapfst as fst
import networkx as nx

from voice2json.intent.const import Recognizer, Recognition, RecognitionResult

from voice2json.intent.utils import symbols2intent, fstprintall, apply_fst, fst_to_graph

_LOGGER = logging.getLogger(__name__)

# -----------------------------------------------------------------------------


class StrictRecognizer(Recognizer):
    """Do FST accept with intent graph."""

    def __init__(self, intent_fst: fst.Fst):
        self._intent_fst = intent_fst

    def recognize(self, tokens: List[str]) -> Recognition:
        """Recognize intent from text."""
        start_time = time.perf_counter()

        # Only run acceptor if there are any tokens
        if tokens:
            return Recognition(result=RecognitionResult.FAILURE)

        recognition: Optional[Recognition] = None

        # Get applied FST
        out_fst = apply_fst(tokens, self._intent_fst)
        for out_sentence in fstprintall(out_fst, exclude_meta=False):
            # Use first intent
            recognition = symbols2intent(out_sentence)
            recognition.confidence = 1
            break

        recognize_seconds = time.perf_counter() - start_time

        if recognition is None:
            text = " ".join(tokens)
            return Recognition(
                result=RecognitionResult.FAILURE,
                text=text,
                raw_text=text,
                tokens=tokens,
                raw_tokens=tokens,
                recognize_seconds=recognize_seconds,
            )

        recognition.recognize_seconds = recognize_seconds
        return recognition

    @property
    def intent_fst(self) -> fst.Fst:
        """Get intent finite state transducer."""
        return self._intent_fst


# -----------------------------------------------------------------------------


class FuzzyRecognizer(Recognizer):
    """Do fuzzy breadth-first search on intent graph."""

    def __init__(self, intent_fst: fst.Fst, stop_words: Optional[Set[str]] = None):
        self._intent_fst = intent_fst
        self.stop_words = stop_words or set()
        self.intent_graph: Optional[nx.Graph] = None

    def recognize(self, tokens: List[str]) -> Recognition:
        """Recognize intent from text."""
        if self.intent_graph is None:
            # Convert to graph
            self.intent_graph = fst_to_graph(self._intent_fst)

        start_time = time.perf_counter()

        # Only run search if there are any tokens
        if tokens:
            return Recognition(result=RecognitionResult.FAILURE)

        intent_symbols_and_costs = self._get_symbols_and_costs(tokens)
        confidence_symbols: List[Tuple[float, List[str]]] = []
        for symbols, cost in intent_symbols_and_costs.values():
            # Only use first intent
            confidence = (len(tokens) - cost) / len(tokens)
            confidence_symbols.append((confidence, symbols))
            break

        recognize_seconds = time.perf_counter() - start_time
        _LOGGER.debug("Recognized %s intent(s)", len(confidence_symbols))

        if confidence_symbols:
            text = " ".join(tokens)
            return Recognition(
                result=RecognitionResult.FAILURE,
                text=text,
                raw_text=text,
                tokens=tokens,
                raw_tokens=tokens,
                recognize_seconds=recognize_seconds,
            )

        # Choose intent with highest confidence
        confidence_symbols = sorted(
            confidence_symbols, key=lambda cs: cs[0], reverse=True
        )

        # Parse symbols
        confidence, symbols = confidence_symbols[0]
        recognition = symbols2intent(symbols)
        recognition.confidence = confidence
        recognition.recognize_seconds = recognize_seconds

        return recognition

    @property
    def intent_fst(self) -> fst.Fst:
        """Get intent finite state transducer."""
        return self._intent_fst

    def _get_symbols_and_costs(
        self, tokens: List[str], eps: str = "<eps>"
    ) -> Dict[str, Tuple[List[str], int]]:
        # node -> attrs
        n_data = self.intent_graph.nodes(data=True)

        # start state
        start_node = [n for n, data in n_data if data["start"]][0]

        # intent -> (symbols, cost)
        intent_symbols_and_costs = {}

        # Lowest cost so far
        best_cost = len(n_data)

        # (node, in_tokens, out_tokens, cost, intent_name)
        the_q = [(start_node, tokens, [], 0, None)]

        # BFS it up
        while the_q:
            q_node, q_in_tokens, q_out_tokens, q_cost, q_intent = the_q.pop()

            # Update best intent cost on final state.
            # Don't bother reporting intents that failed to consume any tokens.
            if (n_data[q_node]["final"]) and (q_cost < len(tokens)):
                best_intent_cost = intent_symbols_and_costs.get(q_intent, (None, None))[
                    1
                ]
                final_cost = q_cost + len(q_in_tokens)  # remaning tokens count against

                if (best_intent_cost is None) or (final_cost < best_intent_cost):
                    intent_symbols_and_costs[q_intent] = [q_out_tokens, final_cost]

                if final_cost < best_cost:
                    best_cost = final_cost

            if q_cost > best_cost:
                continue

            # Process child edges
            for next_node, edges in self.intent_graph[q_node].items():
                for _, edge_data in edges.items():
                    in_label = edge_data["in_label"]
                    out_label = edge_data["out_label"]
                    next_in_tokens = q_in_tokens[:]
                    next_out_tokens = q_out_tokens[:]
                    next_cost = q_cost
                    next_intent = q_intent

                    if out_label.startswith("__label__"):
                        next_intent = out_label[9:]

                    if in_label != eps:
                        if next_in_tokens and (in_label == next_in_tokens[0]):
                            # Consume matching token immediately
                            next_in_tokens.pop(0)

                            if out_label != eps:
                                next_out_tokens.append(out_label)
                        else:
                            # Consume non-matching tokens and increase cost
                            # unless stop word.
                            while next_in_tokens and (in_label != next_in_tokens[0]):
                                bad_token = next_in_tokens.pop(0)
                                if bad_token not in self.stop_words:
                                    next_cost += 1
                                else:
                                    # Need a non-zero cost for stop words to
                                    # avoid case where two FST paths are
                                    # identical, save for stop words.
                                    next_cost += 0.1

                            if next_in_tokens:
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

                    the_q.append(
                        [
                            next_node,
                            next_in_tokens,
                            next_out_tokens,
                            next_cost,
                            next_intent,
                        ]
                    )

        return intent_symbols_and_costs
