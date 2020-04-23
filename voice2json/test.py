"""Methods for testing recorded examples."""
import argparse
import asyncio
import dataclasses
import json
import logging
import shlex
import shutil
import tempfile
import typing
from pathlib import Path

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
    else:
        # Load expected results from examples directory
        assert args.directory, "Examples directory required if no --expected"
        examples_dir = Path(args.directory)
        _LOGGER.debug("Loading expected intents from %s", examples_dir)
        for wav_path in examples_dir.glob("*.wav"):
            json_path = wav_path.with_suffix(".json")
            if json_path.is_file():
                with open(json_path, "r") as json_file:
                    expected[wav_path.name] = Recognition.from_dict(
                        json.load(json_file)
                    )
            else:
                _LOGGER.warning("No JSON file for %s", wav_path)

    if not expected:
        _LOGGER.fatal("No expected examples provided")
        return

    temp_dir = None
    try:
        if not args.actual:
            # Generate actual results from examples directory
            assert args.directory, "Examples directory required if no --expected"
            examples_dir = Path(args.directory)
            _LOGGER.debug("Generating actual intents from %s", examples_dir)

            # Use voice2json and GNU parallel
            assert shutil.which("parallel"), "GNU parallel is required"
            if args.results:
                # Save results to user-specified directory
                results_dir = Path(args.results)
                results_dir.mkdir(parents=True, exist_ok=True)
                _LOGGER.debug("Saving results to %s", results_dir)
            else:
                # Save resuls to temporary directory
                temp_dir = tempfile.TemporaryDirectory()
                results_dir = Path(temp_dir.name)
                _LOGGER.debug(
                    "Saving results to temporary directory (use --results to specify)"
                )

            # Transcribe WAV files
            actual_wavs_path = results_dir / "actual_wavs.txt"
            actual_transcriptions_path = results_dir / "actual_transcriptions.jsonl"

            # Write list of WAV files to a text file
            with open(actual_wavs_path, "w") as actual_wavs_file:
                for wav_path in examples_dir.glob("*.wav"):
                    print(str(wav_path.absolute()), file=actual_wavs_file)

            # Transcribe in parallel
            transcribe_command = [
                "parallel",
                "-k",
                "--pipe",
                "-n",
                str(args.threads),
                "voice2json",
                "-p",
                shlex.quote(str(core.profile_file)),
                "transcribe-wav",
                "--stdin-files",
                "<",
                str(actual_wavs_path),
                ">",
                str(actual_transcriptions_path),
            ]

            _LOGGER.debug(transcribe_command)

            transcribe_process = await asyncio.create_subprocess_shell(
                " ".join(transcribe_command)
            )

            await transcribe_process.wait()
            assert transcribe_process.returncode == 0, "Transcription failed"

            # Recognize intents from transcriptions in parallel
            actual_intents_path = results_dir / "actual_intents.jsonl"
            recognize_command = [
                "parallel",
                "-k",
                "--pipe",
                "-n",
                str(args.threads),
                "voice2json",
                "-p",
                shlex.quote(str(core.profile_file)),
                "recognize-intent",
                "<",
                str(actual_transcriptions_path),
                ">",
                str(actual_intents_path),
            ]

            _LOGGER.debug(recognize_command)

            recognize_process = await asyncio.create_subprocess_shell(
                " ".join(recognize_command)
            )

            await recognize_process.wait()
            assert recognize_process.returncode == 0, "Recognition failed"

            # Load actual intents
            args.actual = actual_intents_path

        assert args.actual, "No actual intents to load"
        _LOGGER.debug("Loading actual intents from %s", args.actual)

        # Load actual results from jsonl file
        with open(args.actual, "r") as actual_file:
            for line in actual_file:
                actual_intent = Recognition.from_dict(json.loads(line))
                assert actual_intent.wav_name, f"No wav_name for {line}"
                actual[actual_intent.wav_name] = actual_intent

        if not actual:
            _LOGGER.fatal("No actual examples provided")
            return

        report = evaluate_intents(expected, actual)
        print_json(dataclasses.asdict(report))
    finally:
        # Delete temporary directory
        if temp_dir:
            temp_dir.cleanup()
