#!/usr/bin/env python3
import io
import re
import json
import argparse
import subprocess
import logging
import time
import shlex
import tempfile
import threading
import wave
import atexit
from uuid import uuid4
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, BinaryIO, List

import pydash
from flask import Flask, request, render_template, send_from_directory, flash, send_file

# -----------------------------------------------------------------------------

profile_path: Optional[Path] = None
profile: Dict[str, Any] = {}

# Flask application
app = Flask("voice2json")
app.secret_key = str(uuid4())

logger = logging.getLogger("app")

# -----------------------------------------------------------------------------

record_proc: Optional[subprocess.Popen] = None
record_file: Optional[BinaryIO] = None
recording: bool = False


@app.route("/", methods=["GET", "POST"])
def index():
    """Handles recording, transcription, and intent recognition."""
    global record_proc, record_file, recording

    # Sentence to recognize
    sentence: str = ""

    # Recognized intent
    intent: Optional[Dict[str, Any]] = None

    # List of (word, entity) tuples from recognized intent
    words_entities: List[Tuple[str, Dict[str, Any]]] = []

    if request.method == "POST":
        # WAV audio data
        wav_data: Optional[bytes] = None

        # Check if start/stopping recording
        if "record" in request.form:
            if record_proc is None:
                # Start recording
                record_file = tempfile.NamedTemporaryFile(mode="wb+")
                record_command = shlex.split(
                    pydash.get(profile, "audio.record-command")
                )
                logger.debug(record_command)

                record_proc = subprocess.Popen(record_command, stdout=record_file)
                recording = True
            else:
                # Stop recording
                record_proc.terminate()
                record_proc.wait()
                record_proc = None
                recording = False

                # Read raw audio data from temp file
                record_file.seek(0)
                raw_audio_data = record_file.read()

                # Convert to WAV data
                with io.BytesIO() as wav_buffer:
                    with wave.open(wav_buffer, mode="wb") as wav_file:
                        wav_file.setframerate(16000)
                        wav_file.setsampwidth(2)
                        wav_file.setnchannels(1)
                        wav_file.writeframesraw(raw_audio_data)

                    wav_data = wav_buffer.getvalue()

                # Clean up
                del record_file
                record_file = None
        elif "upload" in request.form:
            if "wavfile" in request.files:
                # Get WAV data from file upload
                wav_file = request.files["wavfile"]
                wav_data = wav_file.read()
            else:
                flash("No WAV file given", "danger")
        elif "recognize" in request.form:
            # Get sentence to recognize from form
            sentence = request.form["sentence"]
            if len(sentence) == 0:
                flash("No sentence to recognize", "danger")

        # ---------------------------------------------------------------------

        if wav_data is not None:
            # Transcribe WAV
            logger.debug(f"Transcribing {len(wav_data)} byte(s)")
            transcribe_result = json.load(
                voice2json("transcribe-wav", text=False, input=wav_data)
            )
            sentence = transcribe_result.get(
                "raw_text", transcribe_result.get("text", "")
            )

        if len(sentence) > 0:
            # Recognize text
            recognize_result = json.load(
                voice2json("recognize-intent", input=json.dumps(transcribe_result))
            )
            intent = recognize_result

        # Process intent
        if intent is not None:
            char_index = 0

            # Map from start character index to entity
            start_to_entity = {
                e.get("raw_start", -1): e for e in intent.get("entities", [])
            }
            entity = None

            # Go through words (tokens)
            for token in intent.get("raw_tokens", intent.get("tokens", [])):
                if entity and (char_index >= entity.get("raw_end", -1)):
                    # Entity has finished
                    words_entities.append(
                        (entity.get("raw_value", entity.get("value", "")), entity)
                    )
                    entity = None

                if entity is None:
                    # Entity is starting
                    entity = start_to_entity.get(char_index)

                if entity is None:
                    # Regular word
                    words_entities.append((token, None))

                char_index += len(token) + 1  # +1 for space

            if entity:
                # Catch entity at end of sentence
                words_entities.append(
                    (entity.get("raw_value", entity.get("value", "")), entity)
                )

    # -------------------------------------------------------------------------

    # JSON for display to user
    intent_str = json.dumps(intent, indent=4) if intent is not None else ""

    return render_template(
        "index.html",
        profile=profile,
        pydash=pydash,
        sentence=sentence,
        intent=intent,
        intent_str=intent_str,
        words_entities=words_entities,
        recording=recording,
    )


# -----------------------------------------------------------------------------


@app.route("/sentences", methods=["GET", "POST"])
def sentences():
    """Reads/writes sentences.ini. Re-trains when sentences are saved."""
    sentences_path = Path(pydash.get(profile, "training.sentences-file"))

    if request.method == "POST":
        # Save sentences
        sentences_text = request.form["sentences"]
        sentences_path.write_text(sentences_text)
        do_retrain()
    else:
        # Load sentences
        sentences_text = sentences_path.read_text()

    return render_template(
        "sentences.html", profile=profile, pydash=pydash, sentences=sentences_text
    )


# -----------------------------------------------------------------------------


@app.route("/words", methods=["GET", "POST"])
def words():
    """Speaks words, guesses pronunciations, and reads/writes custom_words.txt.
    Re-trains when custom words are saved."""

    custom_words_path = Path(pydash.get(profile, "training.custom-words-file"))
    word = ""

    if request.method == "POST":
        action = request.form["action"]

        if action == "custom words":
            # Save custom words
            custom_words_text = request.form["custom_words"]
            custom_words_path.write_text(custom_words_text)
            do_retrain()
        elif action == "pronounce":
            # Speak or guess pronunciation
            word = request.form["word"]
            is_speak = "speak" in request.form
            if len(word) > 0:
                if is_speak:
                    # Speak pronunciation
                    result = voice2json("pronounce-word", "--nbest", "1", word)
                else:
                    # Get multiple guesses
                    result = voice2json(
                        "pronounce-word", "--quiet", "--nbest", "3", word
                    )

                # Display guess(s)
                for line in result:
                    flash(line.strip(), "info")
            else:
                flash("No word given", "danger")

    # Load custom words
    custom_words_text = custom_words_path.read_text()

    return render_template(
        "words.html",
        profile=profile,
        pydash=pydash,
        custom_words=custom_words_text,
        word=word,
    )


# -----------------------------------------------------------------------------

espeak_words = {}
wav_cache = {}
espeak_cache_dir = tempfile.TemporaryDirectory()

atexit.register(lambda: espeak_cache_dir.cleanup())


@app.route("/phonemes", methods=["GET", "POST"])
def phonemes():
    phoneme_map_path = Path(pydash.get(profile, "text-to-speech.espeak.phoneme-map"))
    phoneme_map = {}

    if request.method == "POST":
        for var_name, var_value in request.form.items():
            if var_name.startswith("espeak_"):
                phoneme = var_name[7:]
                phoneme_map[phoneme] = var_value.strip()

        with open(phoneme_map_path, "w") as phoneme_map_file:
            for phoneme in sorted(phoneme_map):
                print(phoneme, phoneme_map[phoneme], file=phoneme_map_file)

        flash(f"Wrote {phoneme_map_path}", "success")

        # Clear phoneme cache
        for key in list(wav_cache.keys()):
            if key.startswith("phoneme_"):
                wav_cache.pop(key, None)
    else:
        # Load map from dictionary phonemes to eSpeak phonemes
        with open(phoneme_map_path, "r") as phoneme_map_file:
            for line in phoneme_map_file:
                line = line.strip()
                if len(line) == 0 or line.startswith("#"):
                    continue

                dict_phoneme, espeak_phoneme = re.split("\s+", line, maxsplit=1)
                phoneme_map[dict_phoneme] = espeak_phoneme

    # Load word examples for each phoneme
    phoneme_examples_path = Path(
        pydash.get(profile, "speech-to-text.phoneme-examples-file")
    )
    voice = pydash.get(profile, "text-to-speech.espeak.voice", "")
    phoneme_examples = {}

    with open(phoneme_examples_path, "r") as phoneme_examples_file:
        for line in phoneme_examples_file:
            line = line.strip()
            if len(line) == 0 or line.startswith("#"):
                continue

            phoneme, word, pronunciation = re.split(r"\s+", line, maxsplit=2)

            word_cache_key = f"word_{word}"
            phoneme_cache_key = f"phoneme_{phoneme}_{pronunciation.replace(' ', '_')}"

            if word_cache_key not in wav_cache:
                # Speak whole word
                wav_path = Path(espeak_cache_dir.name) / f"{word_cache_key}.wav"
                espeak_cmd = ["espeak-ng", "--sep= ", "-s", "80", "-w", str(wav_path)]
                if len(voice) > 0:
                    espeak_cmd.extend(["-v", str(voice)])

                espeak_cmd.append(word)
                logger.debug(espeak_cmd)
                result = subprocess.check_output(
                    espeak_cmd, universal_newlines=True
                ).strip()

                espeak_word_str = result.replace("'", "")
                espeak_words[word] = espeak_word_str
                wav_cache[word_cache_key] = wav_path

            if phoneme_cache_key not in wav_cache:
                # Speak mapped phonemes
                espeak_phoneme_str = "".join(
                    phoneme_map[p] for p in pronunciation.split()
                )
                wav_path = Path(espeak_cache_dir.name) / f"{phoneme_cache_key}.wav"
                espeak_cmd = ["espeak-ng", "-s", "80", "-w", str(wav_path)]
                logger.debug(espeak_cmd)
                if len(voice) > 0:
                    espeak_cmd.extend(["-v", str(voice)])

                espeak_cmd.append(f"[[{espeak_phoneme_str}]]")
                subprocess.check_call(espeak_cmd)
                wav_cache[phoneme_cache_key] = wav_path

            actual_espeak = " ".join(phoneme_map[p] for p in pronunciation.split())
            phoneme_examples[phoneme] = (word, pronunciation, espeak_words[word], actual_espeak)

    return render_template(
        "phonemes.html",
        sorted=sorted,
        profile=profile,
        pydash=pydash,
        phoneme_examples=phoneme_examples,
        phoneme_map=phoneme_map,
    )


@app.route("/pronounce/<name>", methods=["GET"])
def pronounce(name):
    wav_path = wav_cache[name]
    return send_file(open(wav_path, "rb"), mimetype="audio/wav")


# -----------------------------------------------------------------------------
# Static Routes
# -----------------------------------------------------------------------------


@app.route("/css/<path:filename>", methods=["GET"])
def css(filename):
    return send_from_directory("css", filename)


@app.route("/js/<path:filename>", methods=["GET"])
def js(filename):
    return send_from_directory("js", filename)


@app.route("/img/<path:filename>", methods=["GET"])
def img(filename):
    return send_from_directory("img", filename)


@app.errorhandler(Exception)
def handle_error(err) -> Tuple[str, int]:
    logger.exception(err)
    return (str(err), 500)


# -----------------------------------------------------------------------------
# Utility Methods
# -----------------------------------------------------------------------------


def voice2json(*args, text=True, input=None, stderr=None):
    """Calls voice2json with the given arguments and current profile."""
    global profile_path
    command = ["voice2json"]

    if profile_path is not None:
        # Add profile
        command.extend(["--profile", str(profile_path)])

    command.extend(list(args))
    logger.debug(command)

    if text:
        # Text-based I/O
        return io.StringIO(
            subprocess.check_output(
                command, universal_newlines=True, input=input, stderr=stderr
            )
        )
    else:
        # Binary I/O
        return io.BytesIO(subprocess.check_output(command, input=input, stderr=stderr))


def do_retrain():
    """Re-trains voice2json profile and flashes warnings for unknown words."""
    # Re-train
    start_time = time.time()
    result = voice2json("train-profile", stderr=subprocess.STDOUT).read()
    train_seconds = time.time() - start_time
    flash(f"Re-trained in {train_seconds:0.2f} second(s)", "success")

    logger.debug(result)

    warn_lines = None
    for line in result.splitlines():
        line = line.strip()
        if line.startswith("-") or line.startswith("."):
            continue

        if "unknown" in line:
            warn_lines = []
            line = line + ":"

        if warn_lines is not None:
            warn_lines.append(line)

    if warn_lines is not None:
        flash("\n".join(warn_lines), "warning")


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true", help="Enable DEBUG mode")
    parser.add_argument(
        "--port", type=int, default=5000, help="Web server port (default: 5000)"
    )
    parser.add_argument(
        "--host", default="127.0.0.1", help="Web server host (default: 127.0.0.1)"
    )
    parser.add_argument("--profile", help="Path to voice2json profile")
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)

    logger.debug(args)

    if args.profile is not None:
        profile_path = Path(args.profile)

    # Get profile as JSON from voice2json
    profile = json.load(voice2json("print-profile"))

    # Start web server
    app.run(port=args.port, host=args.host, debug=args.debug)
