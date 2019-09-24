#!/usr/bin/env python3
import sys
import json
from collections import defaultdict

examples_by_intent = defaultdict(list)

# Gather all examples by intent name
for line in sys.stdin:
    example = json.loads(line)
    intent_name = example["intent"]["name"]
    examples_by_intent[intent_name].append(example)

# Write data in RasaNLU markdown training format
for intent_name, examples in examples_by_intent.items():
    print(f"## intent:{intent_name}")

    for example in examples:
        # Create mapping from start/stop character indexes to example entities
        entities_by_start = {e["raw_start"]: e for e in example["entities"]}
        entities_by_end = {e["raw_end"]: e for e in example["entities"]}

        # Current character index
        char_idx = 0

        # Final list of tokens that will be printed for the example
        tokens_to_print = []

        # Current entity
        entity = None

        # Tokens that belong to the current entity
        entity_tokens = []

        # Process "raw" tokens without substitutions
        for token in example["raw_tokens"]:
            if char_idx in entities_by_start:
                # Start entity
                entity = entities_by_start[char_idx]
                entity_tokens = []

            if entity is None:
                # Use token as-is
                tokens_to_print.append(token)
            else:
                # Accumulate into entity token list
                entity_tokens.append(token)

            # Advance character index in raw text
            char_idx += len(token) + 1  # space

            if (char_idx - 1) in entities_by_end:
                # Finish entity
                entity_str = entity["entity"]
                if entity["value"] != entity["raw_value"]:
                    # Include substitution
                    entity_str += f":{entity['value']}"

                # Create Markdown-style entity
                token_str = "[" + " ".join(entity_tokens) + f"]({entity_str})"
                tokens_to_print.append(token_str)
                entity = None

        # Print example
        print("-", " ".join(tokens_to_print))

    # Blank line between intents
    print("")
