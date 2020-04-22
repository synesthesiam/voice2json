"""Methods for testing recorded examples."""
import argparse
import dataclasses
import json
import logging
import sys
import typing

from .core import Voice2JsonCore
from .utils import print_json

_LOGGER = logging.getLogger("voice2json.test")

# -----------------------------------------------------------------------------


async def test_examples(args: argparse.Namespace, core: Voice2JsonCore) -> None:
    """Test speech/intent recognition against a directory of expected results."""
    from rhasspynlu.evaluate import evaluate_intents
    from rhasspynlu.intent import Recognition

    # Make sure profile has been trained
    assert core.check_trained(), "Not trained"

    # Expected/actual intents
    expected: typing.Dict[str, Recognition] = {}
    actual: typing.Dict[str, Recognition] = {}

    if args.expected:
        _LOGGER.debug("Loading expected intents from %s", args.expected)

        # Load expected results from jsonl file.
        # Each line is an intent with a wav_name key.
        with open(args.expected, "r") as expected_file:
            for line in expected_file:
                expected_intent = Recognition.from_dict(json.loads(line))
                assert expected_intent.wav_name, f"No wav_name for {line}"
                expected[expected_intent.wav_name] = expected_intent

    if not expected:
        _LOGGER.fatal("No expected examples provided")
        sys.exit(1)

    if args.actual:
        _LOGGER.debug("Loading actual intents from %s", args.actual)

        # Load actual results from jsonl file
        with open(args.actual, "r") as actual_file:
            for line in actual_file:
                actual_intent = Recognition.from_dict(json.loads(line))
                assert actual_intent.wav_name, f"No wav_name for {line}"
                actual[actual_intent.wav_name] = actual_intent

    if not actual:
        _LOGGER.fatal("No actual examples provided")
        sys.exit(1)

    report = evaluate_intents(expected, actual)
    print_json(dataclasses.asdict(report))
