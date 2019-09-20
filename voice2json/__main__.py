#!/usr/bin/env python3

import sys
import re
import io
import os
import json
import time
import argparse
import logging
import tempfile
import subprocess
import threading
import shutil
from pathlib import Path
from collections import defaultdict
from typing import Set, Dict, Optional, List, Any, BinaryIO

logger = logging.getLogger("voice2json")

import yaml
import pydash
import jsonlines

from voice2json.utils import ppath

# -----------------------------------------------------------------------------


def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="voice2json")
    parser.add_argument("--profile", "-p", help="Path to profle directory")
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG log to console"
    )

    sub_parsers = parser.add_subparsers()
    sub_parsers.required = True
    sub_parsers.dest = "command"

    # train-profile
    train_parser = sub_parsers.add_parser(
        "train-profile", help="Train voice2json profile"
    )
    train_parser.set_defaults(func=train)

    # transcribe-wav
    transcribe_parser = sub_parsers.add_parser(
        "transcribe-wav", help="Transcribe WAV file to text"
    )
    transcribe_parser.set_defaults(func=transcribe)
    transcribe_parser.add_argument(
        "wav_file", nargs="*", default=[], help="Path(s) to WAV file(s)"
    )

    # recognize-text
    recognize_parser = sub_parsers.add_parser(
        "recognize-text", help="Recognize JSON intent from text"
    )
    recognize_parser.set_defaults(func=recognize)
    recognize_parser.add_argument(
        "sentence", nargs="*", default=[], help="Sentences to recognize"
    )
    recognize_parser.add_argument(
        "--text-input", action="store_true", help="Input is plain text instead of JSON"
    )

    # record-command
    command_parser = sub_parsers.add_parser(
        "record-command",
        help="Record voice command from stdin audio, write WAV to stdout",
    )
    command_parser.set_defaults(func=record_command)

    # wait-wake
    wake_parser = sub_parsers.add_parser(
        "wait-wake", help="Listen to audio from stdin, wait until wake word is spoken"
    )
    wake_parser.set_defaults(func=wake)

    # pronounce-word
    pronounce_parser = sub_parsers.add_parser(
        "pronounce-word", help="Speak a word phonetically"
    )
    pronounce_parser.add_argument("word", nargs="*", help="Word(s) to prononunce")
    pronounce_parser.add_argument(
        "--quiet", action="store_true", help="Don't speak word; only print phonemes"
    )
    pronounce_parser.add_argument(
        "--delay", type=float, default=0, help="Seconds to wait between words"
    )
    pronounce_parser.set_defaults(func=pronounce)

    # generate-sentences
    generate_parser = sub_parsers.add_parser(
        "generate-sentences", help="Randomly generate sentences from profile"
    )
    generate_parser.add_argument(
        "--samples", type=int, required=True, help="Number of sentences to generate"
    )
    generate_parser.add_argument(
        "--meta", action="store_true", help="Include meta tags"
    )
    generate_parser.set_defaults(func=generate)

    # record-examples
    record_examples_parser = sub_parsers.add_parser(
        "record-examples",
        help="Randomly generate example prompts and have the user record them",
    )
    record_examples_parser.add_argument(
        "--directory", help="Directory to save recorded WAV files and transcriptions"
    )
    record_examples_parser.add_argument(
        "--audio_source", help="File to read raw 16-bit 16Khz mono audio from"
    )
    record_examples_parser.add_argument(
        "--chunk-size",
        type=int,
        default=1024,
        help="Number of bytes to read at a time from stdin",
    )
    record_examples_parser.set_defaults(func=record_examples)

    # test-examples
    test_examples_parser = sub_parsers.add_parser(
        "test-examples", help="Test performance on previously recorded examples"
    )
    test_examples_parser.add_argument(
        "--directory", help="Directory with recorded examples"
    )
    test_examples_parser.add_argument(
        "--results", help="Directory to save test results"
    )
    test_examples_parser.set_defaults(func=test_examples)

    # tune-examples
    tune_examples_parser = sub_parsers.add_parser(
        "tune-examples", help="Tune speech recognizer with previously recorded examples"
    )
    tune_examples_parser.add_argument(
        "--directory", help="Directory with recorded examples"
    )
    tune_examples_parser.set_defaults(func=tune_examples)

    # -------------------------------------------------------------------------

    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)

    logger.debug(args)

    if args.profile is None:
        # Guess profile location in $HOME/.config/voice2json
        if "XDG_CONFIG_HOME" in os.environ:
            config_home = Path(os.environ["XDG_CONFIG_HOME"])
        else:
            config_home = Path("~/.config").expanduser()

        profile_dir = config_home / "voice2json"
        logger.debug(f"Assuming profile is at {profile_dir}")

    else:
        # Use profile provided on command line
        profile_dir = Path(args.profile)

    # Set environment variable usually referenced in profile
    os.environ["profile_dir"] = str(profile_dir)

    # Load profile
    profile_yaml = profile_dir / "profile.yml"
    logger.debug(f"Loading profile from {profile_yaml}")

    with open(profile_yaml, "r") as profile_file:
        profile = yaml.safe_load(profile_file)

    # Call sub-commmand
    args.func(args, profile_dir, profile)


# -----------------------------------------------------------------------------


def train(args: argparse.Namespace, profile_dir: Path, profile: Dict[str, Any]) -> None:
    from voice2json.train import train_profile

    # Strip voice2json command-line arguments so doit won't pick them up
    sys.argv = [sys.argv[0]]

    train_profile(profile_dir, profile)


# -----------------------------------------------------------------------------


def transcribe(
    args: argparse.Namespace, profile_dir: Path, profile: Dict[str, Any]
) -> None:
    from voice2json import get_transcriber

    transcriber = get_transcriber(profile_dir, profile, debug=args.debug)

    if len(args.wav_file) > 0:
        for wav_path_str in args.wav_file:
            # Load and convert
            wav_path = Path(wav_path_str)
            logger.debug(f"Transcribing {wav_path}")

            wav_data = wav_path.read_bytes()

            # Transcribe
            result = transcriber.transcribe_wav(wav_data)

            # Add name of WAV file to result
            result["wav_name"] = wav_path.name

            print_json(result)
    else:
        # Read WAV data from stdin
        logger.debug("Reading WAV data from stdin")

        # Load and convert
        wav_data = sys.stdin.buffer.read()

        # Transcribe
        result = transcriber.transcribe_wav(wav_data)
        print_json(result)


# -----------------------------------------------------------------------------


def recognize(
    args: argparse.Namespace, profile_dir: Path, profile: Dict[str, Any]
) -> None:
    from voice2json import get_recognizer

    # Load intent recognizer
    recognizer = get_recognizer(profile_dir, profile)

    if len(args.sentence) > 0:
        sentences = args.sentence
    else:
        logger.debug("Reading sentences from stdin")
        sentences = sys.stdin

    # Process sentences
    for sentence in sentences:
        if args.text_input:
            # Input is plain text
            text = sentence
            sentence_object = {"text": text}
        else:
            # Input is JSON
            sentence_object = json.loads(sentence)
            text = sentence_object.get("text", "")

        intent = recognizer.recognize(text)

        # Merge with input object
        for key, value in intent.items():
            sentence_object[key] = value

        print_json(sentence_object)


# -----------------------------------------------------------------------------


def record_command(
    args: argparse.Namespace, profile_dir: Path, profile: Dict[str, Any]
) -> None:
    from voice2json.command.webrtcvad import wait_for_command
    from voice2json.utils import buffer_to_wav

    logger.debug("Recording raw 16-bit 16Khz mono audio from stdin")

    audio_buffer = wait_for_command(sys.stdin.buffer)
    wav_bytes = buffer_to_wav(audio_buffer)
    sys.stdout.buffer.write(wav_bytes)


# -----------------------------------------------------------------------------


def wake(args: argparse.Namespace, profile_dir: Path, profile: Dict[str, Any]) -> None:
    import struct
    from voice2json.wake.porcupine import Porcupine

    # Load settings
    library_path = ppath(profile, profile_dir, "wake-word.library-file")
    params_path = ppath(profile, profile_dir, "wake-word.params-file")
    keyword_path = ppath(profile, profile_dir, "wake-word.keyword-file")
    sensitivity = float(pydash.get(profile, "wake-word.sensitivity", 0.5))

    # Load porcupine
    handle = Porcupine(
        str(library_path),
        str(params_path),
        keyword_file_paths=[str(keyword_path)],
        sensitivities=[sensitivity],
    )

    chunk_size = handle.frame_length * 2
    chunk_format = "h" * handle.frame_length

    # Process audio
    logger.debug("Recording raw 16-bit 16Khz mono audio from stdin")

    chunk = sys.stdin.buffer.read(chunk_size)
    while len(chunk) == chunk_size:
        # Process audio chunk
        chunk = struct.unpack_from(chunk_format, chunk)
        keyword_index = handle.process(chunk)

        if keyword_index:
            result = {"keyword": str(keyword_path)}
            print_json(result)

        chunk = sys.stdin.buffer.read(chunk_size)


# -----------------------------------------------------------------------------


def pronounce(
    args: argparse.Namespace, profile_dir: Path, profile: Dict[str, Any]
) -> None:
    from voice2json.utils import read_dict

    base_dictionary_path = ppath(
        profile, profile_dir, "training.base_dictionary", "base_dictionary.txt"
    )
    dictionary_path = ppath(
        profile, profile_dir, "training.dictionary", "dictionary.txt"
    )
    g2p_path = ppath(profile, profile_dir, "training.g2p-model", "g2p.fst")
    g2p_exists = g2p_path.exists()

    map_path = ppath(
        profile, profile_dir, "text-to-speech.phoneme-map", "espeak_phonemes.txt"
    )
    map_exists = map_path.exists()

    # Load dictionaries
    pronunciations: Dict[str, List[str]] = defaultdict(list)

    for dict_path in [dictionary_path, base_dictionary_path]:
        if dict_path.exists():
            with open(dict_path, "r") as dict_file:
                read_dict(dict_file, pronunciations)

    if len(args.word) > 0:
        words = args.word
    else:
        words = sys.stdin

    # Process words
    for word in words:
        word = word.strip()
        dict_phonemes = None

        if word in pronunciations:
            # Use first pronunciation in dictionary
            dict_phonemes = re.split(r"\s+", pronunciations[word][0])
        elif g2p_exists:
            # Guess pronunciation with phonetisaurus
            logger.debug(f"Guessing pronunciation for {word}")

            with tempfile.NamedTemporaryFile(mode="w") as word_file:
                print(word, file=word_file)
                word_file.seek(0)

                phonetisaurus_cmd = [
                    "phonetisaurus-apply",
                    "--model",
                    str(g2p_path),
                    "--word_list",
                    word_file.name,
                    "--nbest",
                    "1",
                ]

                logger.debug(phonetisaurus_cmd)
                output_lines = (
                    subprocess.check_output(phonetisaurus_cmd).decode().splitlines()
                )
                dict_phonemes = re.split(r"\s+", output_lines[0].strip())[1:]
        else:
            logger.warn(f"No pronunciation for {word}")

        if dict_phonemes is not None:
            print(word, " ".join(dict_phonemes))

        if not args.quiet:
            if map_exists:
                # Map to espeak phonemes
                phoneme_map = dict(
                    re.split(r"\s+", line.strip(), maxsplit=1)
                    for line in map_path.read_text().splitlines()
                )

                espeak_phonemes = [phoneme_map[p] for p in dict_phonemes]
            else:
                espeak_phonemes = dict_phonemes

            # Speak with espeak
            espeak_str = "".join(espeak_phonemes)
            espeak_cmd = ["espeak", "-s", "80", f"[[{espeak_str}]]"]
            logger.debug(espeak_cmd)
            subprocess.check_call(espeak_cmd)

            time.sleep(args.delay)


# -----------------------------------------------------------------------------


def generate(
    args: argparse.Namespace, profile_dir: Path, profile: Dict[str, Any]
) -> None:
    import pywrapfst as fst
    from voice2json.train.jsgf2fst import fstprintall

    # Load settings
    intent_fst_path = ppath(
        profile, profile_dir, "intent-recognition.intent-fst", "intent.fst"
    )

    # Load intent finite state transducer
    intent_fst = fst.Fst.read(str(intent_fst_path))

    # Generate samples
    rand_fst = fst.randgen(intent_fst, npath=args.samples)

    # Print samples
    fstprintall(rand_fst, out_file=sys.stdout, exclude_meta=(not args.meta))


# -----------------------------------------------------------------------------


def record_examples(
    args: argparse.Namespace, profile_dir: Path, profile: Dict[str, Any]
) -> None:
    import pywrapfst as fst
    from voice2json.utils import buffer_to_wav
    from voice2json.train.jsgf2fst import fstprintall, symbols2intent

    chunk_size = args.chunk_size
    examples_dir = Path(args.directory) if args.directory is not None else Path.cwd()
    examples_dir.mkdir(parents=True, exist_ok=True)

    # Load settings
    intent_fst_path = ppath(
        profile, profile_dir, "intent-recognition.intent-fst", "intent.fst"
    )

    # Load intent finite state transducer
    intent_fst = fst.Fst.read(str(intent_fst_path))

    def generate_intent() -> Dict[str, Any]:
        # Generate sample sentence
        rand_fst = fst.randgen(intent_fst, npath=1)

        # Convert to words/tokens
        symbols = fstprintall(rand_fst, exclude_meta=False)[0]

        # Convert to intent
        return symbols2intent(symbols)

    def get_wav_path(text: str, count: int) -> Path:
        # /dir/the_transcription_text-000.wav
        text = re.sub(r"\s+", "_", text)
        return examples_dir / f"{text}-{count:03d}.wav"

    # Expected raw 16-bit, 16Khz mono audio
    if args.audio_source is None:
        arecord_cmd = [
            "arecord",
            "-q",
            "-r",
            "16000",
            "-c",
            "1",
            "-f",
            "S16_LE",
            "-t",
            "raw",
        ]
        arecord_proc = subprocess.Popen(arecord_cmd, stdout=subprocess.PIPE)
        audio_source = arecord_proc.stdout
        logger.debug(f"Recording raw 16-bit 16Khz mono audio using arecord")
    else:
        audio_source: BinaryIO = open(args.audio_source, "rb")
        logger.debug(f"Recording raw 16-bit 16Khz mono audio from {args.audio_source}")

    # Recording thread
    audio_data = bytes()
    recording = False

    def record_audio():
        nonlocal audio_source, recording, audio_data
        while audio_source is not None:
            chunk = audio_source.read(chunk_size)
            if recording:
                audio_data += chunk

    record_thread = threading.Thread(target=record_audio, daemon=True)
    record_thread.start()

    try:
        while True:
            # Generate random intent for prompt
            random_intent = generate_intent()
            text = random_intent["text"]

            # Prompt
            print("---")
            print(text)

            # Instructions
            print("Press ENTER to start recording (CTRL+C to exit)")
            input()

            # Record
            audio_data = bytes()
            recording = True

            # Instructions
            print("Recording from stdin. Press ENTER to stop (CTRL+C to exit).")
            input()

            # Save WAV
            recording = False
            logging.debug(f"Recorded {len(audio_data)} byte(s) of audio data")

            count = 0
            wav_path = get_wav_path(text, count)
            while wav_path.exists():
                # Find unique name
                count += 1
                wav_path = get_wav_path(text, count)

            wav_bytes = buffer_to_wav(audio_data)
            wav_path.write_bytes(wav_bytes)

            # Save transcription
            transcript_path = examples_dir / f"{wav_path.stem}.txt"
            transcript_path.write_text(text)

            # Save intent
            intent_path = examples_dir / f"{wav_path.stem}.json"
            with open(intent_path, "w") as intent_file:
                with jsonlines.Writer(intent_file) as out:
                    out.write(random_intent)

            # Response
            print("Wrote", wav_path)
            print("")

    except KeyboardInterrupt:
        audio_source = None
        record_thread.join()


# -----------------------------------------------------------------------------


def test_examples(
    args: argparse.Namespace, profile_dir: Path, profile: Dict[str, Any]
) -> None:
    from voice2json import get_transcriber, get_recognizer

    examples_dir = Path(args.directory) if args.directory is not None else Path.cwd()
    logger.debug(f"Looking for examples in {examples_dir}")

    results_dir = None
    if args.results is not None:
        results_dir = Path(args.results)

    # Load WAV transcriber
    transcriber = get_transcriber(profile_dir, profile, debug=args.debug)

    # Optional intent recognizer
    recognizer = None

    # ----------
    # Statistics
    # ----------

    # Total number of WAV files
    num_wavs = 0

    # Number transcriptions that match *exactly*
    correct_transcriptions = 0

    # Number of words in all transcriptions (as counted by word_align.pl)
    num_words = 0

    # Number of correct words in all transcriptions (as computed by word_align.pl)
    correct_words = 0

    # Number of recognized intents that match expectations
    correct_intent_names = 0

    # Number of entity/value pairs that match *exactly* in all recognized intents
    correct_entities = 0

    # Number of entity/value pairs all intents
    num_entities = 0

    # Expected/actual intents
    expected: Dict[str, Dict[str, Any]] = {}
    actual: Dict[str, Dict[str, Any]] = {}

    # Process examples
    for wav_path in examples_dir.glob("*.wav"):
        logger.debug(f"Processing {wav_path}")

        # Load expected transcription
        transcript_path = examples_dir / f"{wav_path.stem}.txt"
        expected_text = None

        if transcript_path.exists():
            expected_text = transcript_path.read_text().strip()

        # Load expected intent (optional)
        intent_path = examples_dir / f"{wav_path.stem}.json"
        expected_intent = None
        if intent_path.exists():
            with open(intent_path, "r") as intent_file:
                expected_intent = json.load(intent_file)

            # Use full intent
            expected[wav_path.name] = expected_intent
        else:
            # Use text only
            expected[wav_path.name] = {"text": expected_text}

        if (expected_text is None) and (expected_intent is None):
            logger.warn(f"Skipping {wav_path} (no transcription or intent files)")
            continue
        elif expected_text is None:
            # Use text from intent
            expected_text = expected_intent["text"]

        # Transcribe WAV
        wav_data = wav_path.read_bytes()
        actual_transcription = transcriber.transcribe_wav(wav_data)
        actual_text = actual_transcription["text"]
        logger.debug(actual_text)

        if expected_text == actual_text:
            correct_transcriptions += 1

        # Do recognition
        if expected_intent is not None:
            if recognizer is None:
                # Load recognizer on demand
                recognizer = get_recognizer(profile_dir, profile)

            actual_intent = recognizer.recognize(actual_text)
            logger.debug(actual_intent)

            if expected_intent["intent"]["name"] == actual_intent["intent"]["name"]:
                correct_intent_names += 1

                # Only check entities if intent was correct
                expected_entities: List[Tuple[str, str]] = []
                for entity_dict in expected_intent.get("entities", []):
                    num_entities += 1
                    entity_tuple = (entity_dict["entity"], entity_dict["value"])
                    expected_entities.append(entity_tuple)

                # Verify actual entities
                for entity_dict in actual_intent.get("entities", []):
                    entity_tuple = (entity_dict["entity"], entity_dict["value"])

                    if entity_tuple in expected_entities:
                        correct_entities += 1
                        expected_entities.remove(entity_tuple)

            # Record full intent
            actual[wav_path.name] = actual_intent
        else:
            # Record transcription result only
            actual[wav_path.name] = actual_transcription

        num_wavs += 1

    # Compute word error rate (WER)
    align_results: Dict[str, Any] = {}
    if shutil.which("word_align.pl"):
        from voice2json.utils import align2json

        with tempfile.NamedTemporaryFile(mode="w") as reference_file:
            # Write references
            for expected_key, expected_intent in expected.items():
                print(expected_intent["text"], f"({expected_key})", file=reference_file)

            with tempfile.NamedTemporaryFile(mode="w") as hypothesis_file:
                # Write hypotheses
                for actual_key, actual_intent in actual.items():
                    print(
                        actual_intent["text"], f"({actual_key})", file=hypothesis_file
                    )

                # Calculate WER
                reference_file.seek(0)
                hypothesis_file.seek(0)

                align_cmd = ["word_align.pl", reference_file.name, hypothesis_file.name]
                logger.debug(align_cmd)

                align_output = subprocess.check_output(align_cmd).decode()
                if results_dir is not None:
                    align_output_path = results_dir / "word_align.txt"
                    align_output_path.write_text(align_output)
                    logger.debug(f"Wrote {align_output_path}")

                # Convert to JSON
                with io.StringIO(align_output) as align_file:
                    align_results = align2json(align_file)

    else:
        logger.warn("word_align.pl not found in PATH. Not computing WER.")

    # Merge WER results
    for key, wer in align_results.items():
        actual[key]["word_error"] = wer
        num_words += wer["words"]
        correct_words += wer["correct"]

    # Summarize results
    summary = {
        "statistics": {
            "num_wavs": num_wavs,
            "num_words": num_words,
            "num_entities": num_entities,
            "correct_transcriptions": correct_transcriptions,
            "correct_intent_names": correct_intent_names,
            "correct_words": correct_words,
            "correct_entities": correct_entities,
            "transcription_accuracy": correct_words / num_words if num_words > 0 else 1,
            "intent_accuracy": correct_intent_names / num_wavs if num_wavs > 0 else 1,
            "entity_accuracy": correct_entities / num_entities
            if num_entities > 0
            else 1,
        },
        "actual": actual,
        "expected": expected,
    }

    print_json(summary)


# -----------------------------------------------------------------------------


def tune_examples(
    args: argparse.Namespace, profile_dir: Path, profile: Dict[str, Any]
) -> None:
    from voice2json import get_tuner

    examples_dir = Path(args.directory) if args.directory is not None else Path.cwd()
    logger.debug(f"Looking for examples in {examples_dir}")

    start_time = time.time()

    tuner = get_tuner(profile_dir, profile)
    tuner.tune(examples_dir)

    end_time = time.time()
    print("Tuning completed in", end_time - start_time, "second(s)")


# -----------------------------------------------------------------------------
# Utilities
# -----------------------------------------------------------------------------


def print_json(value: Any) -> None:
    """Prints a single line of JSON to stdout."""
    with jsonlines.Writer(sys.stdout) as out:
        out.write(value)


def env_constructor(loader, node):
    """Expands !env STRING to replace environment variables in STRING."""
    return os.path.expandvars(node.value)


yaml.SafeLoader.add_constructor("!env", env_constructor)

# -----------------------------------------------------------------------------


if __name__ == "__main__":
    main()
