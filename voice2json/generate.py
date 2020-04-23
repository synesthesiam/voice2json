"""Methods for generating examples."""
import argparse
import dataclasses
import gzip
import logging

from .core import Voice2JsonCore
from .utils import dag_paths_random, itershuffle, print_json

_LOGGER = logging.getLogger("voice2json.generate")

# -----------------------------------------------------------------------------


async def generate(args: argparse.Namespace, core: Voice2JsonCore) -> None:
    """Generate randomish examples from intent graph."""
    import networkx as nx
    import rhasspynlu

    # Make sure profile has been trained
    assert core.check_trained(), "Not trained"

    # Load settings
    intent_graph_path = core.ppath(
        "intent-recognition.intent-graph", "intent.pickle.gz"
    )

    # Load intent graph
    _LOGGER.debug("Loading %s", intent_graph_path)
    with gzip.GzipFile(intent_graph_path, mode="rb") as graph_gzip:
        intent_graph = nx.readwrite.gpickle.read_gpickle(graph_gzip)

    start_node, end_node = rhasspynlu.jsgf_graph.get_start_end_nodes(intent_graph)
    assert (start_node is not None) and (
        end_node is not None
    ), "Missing start/end node(s)"

    paths_left = None
    if args.number > 0:
        paths_left = args.number

    # Iterate through all paths
    for path in itershuffle(dag_paths_random(intent_graph, start_node, end_node)):
        if paths_left is not None:
            paths_left -= 1
            if paths_left < 0:
                # Stop iterating
                break

        if args.raw_symbols:
            # Output labels directly from intent graph
            symbols = []
            for from_node, to_node in rhasspynlu.utils.pairwise(path):
                edge_data = intent_graph.edges[(from_node, to_node)]
                olabel = edge_data.get("olabel")
                if olabel:
                    symbols.append(olabel)

            print(" ".join(symbols))
            continue

        # Convert to intent
        _, recognition = rhasspynlu.fsticuffs.path_to_recognition(path, intent_graph)
        if not recognition:
            _LOGGER.warning("Recognition failed for path: %s", path)
            continue

        intent = dataclasses.asdict(recognition)

        # Add slots
        intent["slots"] = {}
        for ev in intent["entities"]:
            intent["slots"][ev["entity"]] = ev["value"]

        if args.iob:
            # IOB format
            token_idx = 0
            entity_start = {ev["start"]: ev for ev in intent["entities"]}
            entity_end = {ev["end"]: ev for ev in intent["entities"]}
            entity = None

            word_tags = []
            for word in intent["tokens"]:
                # Determine tag label
                tag = "O" if not entity else f"I-{entity}"
                if token_idx in entity_start:
                    entity = entity_start[token_idx]["entity"]
                    tag = f"B-{entity}"

                word_tags.append((word, tag))

                # word ner
                token_idx += len(word) + 1

                if (token_idx - 1) in entity_end:
                    entity = None

            print("BS", end=" ")
            for wt in word_tags:
                print(wt[0], end=" ")
            print("ES", end="\t")

            print("O", end=" ")  # BS
            for wt in word_tags:
                print(wt[1], end=" ")
            print("O", end="\t")  # ES

            # Intent name last
            print(intent["intent"]["name"])
        else:
            # Write as jsonl
            print_json(intent)
