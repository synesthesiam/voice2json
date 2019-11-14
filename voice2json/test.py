#!/usr/bin/env python3
import io
import os
import re
import sys
import json
import tempfile
import unittest
import logging
import argparse
import subprocess
from pathlib import Path

logging.basicConfig(level=logging.DEBUG)

global voice2json_dir
profile_dirs = []

# -----------------------------------------------------------------------------


class Voice2JsonTestCase(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        self.test_dir = voice2json_dir / "etc" / "test"
        unittest.TestCase.__init__(self, *args, **kwargs)

    def test_wait_wake(self):
        """Tests the wait-wake command."""
        correct_wav = self.test_dir / "porcupine.wav"
        incorrect_wav = self.test_dir / "what_time_is_it.wav"
        wake_cmd = ["voice2json", "wait-wake", "--audio-source", "-"]

        # Check WAV with keyword
        correct_output = (
            subprocess.check_output(wake_cmd, input=correct_wav.read_bytes())
            .decode()
            .strip()
        )

        self.assertTrue(len(correct_output) > 0)

        # { "keyword": "...", "detect_seconds": ... }
        correct_json = json.loads(correct_output)
        self.assertIn("keyword", correct_json)
        self.assertIn("detect_seconds", correct_json)

        # Check WAV without keyword
        incorrect_output = (
            subprocess.check_output(wake_cmd, input=incorrect_wav.read_bytes())
            .decode()
            .strip()
        )

        # No output expected
        self.assertTrue(len(incorrect_output) == 0)

    def test_record_command(self):
        """Tests the record-command command."""
        command_wav = self.test_dir / "turn_on_living_room_lamp.wav"
        command_output = (
            subprocess.check_output(
                [
                    "voice2json",
                    "record-command",
                    "--wav-sink",
                    "/dev/null",
                    "--audio-source",
                    "-",
                ],
                input=command_wav.read_bytes(),
            )
            .decode()
            .strip()
        )

        self.assertTrue(len(command_output) > 0)

        # Check events
        start_seconds = None
        stop_seconds = None
        with io.StringIO(command_output) as command_file:
            for line in command_file:
                event = json.loads(line)
                if event["event"] == "started":
                    start_seconds = event["time_seconds"]
                elif event["event"] == "stopped":
                    stop_seconds = event["time_seconds"]

        self.assertIsNotNone(start_seconds, "Missing started")
        self.assertIsNotNone(stop_seconds, "Missing stopped")

        # Stop time should be later
        self.assertGreater(stop_seconds, start_seconds)


# -----------------------------------------------------------------------------


class ProfileTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Train all profiles before running tests
        for profile_dir in profile_dirs:
            subprocess.check_call(
                ["voice2json", "--profile", str(profile_dir), "train-profile"]
            )

    # -------------------------------------------------------------------------

    def _get_report(self, profile_dir):
        """Use test-examples command to generate a transcription/recognition report."""
        return json.loads(
            subprocess.check_output(
                [
                    "voice2json",
                    "--profile",
                    str(profile_dir),
                    "test-examples",
                    "--directory",
                    str(profile_dir / "test" / "perfect"),
                ]
            )
        )

    def test_examples(self):
        """Check transcriptions and recognized intents for test WAV file(s)."""
        for profile_dir in profile_dirs:
            with self.subTest(profile_dir):
                report = self._get_report(profile_dir)
                stats = report["statistics"]

                # Should be perfect
                self.assertEqual(1, stats["intent_entity_accuracy"])

    # -------------------------------------------------------------------------

    def _get_phonemes(self, profile_dir, word):
        """Use pronounce-word command to get actual or guessed phonemes for a word."""
        # word P1 P2 P3...
        return re.split(
            r"\s+",
            subprocess.check_output(
                [
                    "voice2json",
                    "--profile",
                    str(profile_dir),
                    "pronounce-word",
                    "--quiet",
                    "--nbest",
                    "1",
                    word,
                ]
            )
            .decode()
            .strip(),
            maxsplit=1,
        )[1]

    def test_g2p(self):
        """Test dictionary lookup with known word and grapheme-to-phoneme model with unknown word."""
        for profile_dir in profile_dirs:
            with self.subTest(profile_dir):
                test_dir = profile_dir / "test"

                # { "known": { "word": "...", "phonemes": "..." },
                #   "unknown": { "word": "...", "phonemes": "..." } }
                with open(test_dir / "g2p.json", "r") as g2p_test_file:
                    g2p_test = json.load(g2p_test_file)

                # Check known word
                known_phonemes = self._get_phonemes(
                    profile_dir, g2p_test["known"]["word"]
                )
                self.assertEqual(g2p_test["known"]["phonemes"], known_phonemes)

                # Check unknown word
                unknown_phonemes = self._get_phonemes(
                    profile_dir, g2p_test["unknown"]["word"]
                )
                self.assertEqual(g2p_test["unknown"]["phonemes"], unknown_phonemes)


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--voice2json", help="Directory with voice2json source code")
    parser.add_argument(
        "--profile", "-p", action="append", default=[], help="Include profile in test"
    )
    prog_name = sys.argv[0]
    args, rest = parser.parse_known_args()

    voice2json_dir = Path(args.voice2json or os.getcwd())

    for profile_dir in args.profile:
        profile_dirs.append(Path(profile_dir))

    argv = [prog_name] + rest
    unittest.main(argv=argv)
