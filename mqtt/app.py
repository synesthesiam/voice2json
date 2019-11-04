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
import base64
import asyncio
from uuid import uuid4
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, BinaryIO, List

import pydash
import paho.mqtt.client as mqtt
from quart import Quart, request, render_template, send_from_directory, flash, send_file

from utils import voice2json, buffer_to_wav, maybe_convert_wav, wav_to_buffer

# -----------------------------------------------------------------------------

# MQTT topics
TOPIC_TRANSCRIBE_AUDIO_IN = "voice2json/transcribe-wav/audio-in"
TOPIC_TRANSCRIPTION = "voice2json/transcribe-wav/transcription"
TOPIC_RECOGNIZE = "voice2json/recognize-intent/recognize"
TOPIC_INTENT = "voice2json/recognize-intent/intent"
TOPIC_TRAIN = "voice2json/train-profile/train"
TOPIC_TRAINED = "voice2json/train-profile/trained"
sub_topics = [TOPIC_INTENT, TOPIC_TRANSCRIPTION, TOPIC_TRAINED]

profile_path: Optional[Path] = None
profile: Dict[str, Any] = {}
client = None
chunk_size = 960

# Quart application
app = Quart("voice2json")
app.secret_key = str(uuid4())

logger = logging.getLogger("app")
loop = asyncio.get_event_loop()

# -----------------------------------------------------------------------------

record_proc: Optional[subprocess.Popen] = None
record_file: Optional[BinaryIO] = None
recording: bool = False

mqtt_transcription_queue = asyncio.Queue()
mqtt_intent_queue = asyncio.Queue()
mqtt_train_queue = asyncio.Queue()

# -----------------------------------------------------------------------------


@app.route("/", methods=["GET", "POST"])
async def index():
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
        form = await request.form
        if "record" in form:
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
                wav_data = buffer_to_wav(raw_audio_data)

                # Clean up
                del record_file
                record_file = None
        elif "upload" in form:
            files = await request.files
            if "wavfile" in files:
                # Get WAV data from file upload
                wav_file = files["wavfile"]
                wav_data = wav_file.read()
            else:
                await flash("No WAV file given", "danger")
        elif "recognize" in form:
            # Get sentence to recognize from form
            sentence = form["sentence"]
            if len(sentence) == 0:
                await flash("No sentence to recognize", "danger")

            transcribe_result = {"text": sentence.strip()}

        # ---------------------------------------------------------------------

        if wav_data is not None:
            # Transcribe WAV
            logger.debug(f"Transcribing {len(wav_data)} byte(s)")
            stream_wav(TOPIC_TRANSCRIBE_AUDIO_IN, wav_data)
            transcribe_result = await mqtt_transcription_queue.get()
            sentence = transcribe_result.get(
                "raw_text", transcribe_result.get("text", "")
            )

        if len(sentence) > 0:
            # Recognize text
            client.publish(TOPIC_RECOGNIZE, json.dumps(transcribe_result))
            intent = await mqtt_intent_queue.get()

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

    return await render_template(
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
async def sentences():
    """Reads/writes sentences.ini. Re-trains when sentences are saved."""
    sentences_path = Path(pydash.get(profile, "training.sentences-file"))

    if request.method == "POST":
        # Save sentences
        form = await request.form
        sentences_text = form["sentences"]
        sentences_path.write_text(sentences_text)
        await do_retrain()
    else:
        # Load sentences
        sentences_text = sentences_path.read_text()

    return await render_template(
        "sentences.html", profile=profile, pydash=pydash, sentences=sentences_text
    )


# -----------------------------------------------------------------------------


@app.route("/words", methods=["GET", "POST"])
async def words():
    """Speaks words, guesses pronunciations, and reads/writes custom_words.txt.
    Re-trains when custom words are saved."""

    custom_words_path = Path(pydash.get(profile, "training.custom-words-file"))
    word = ""
    guesses = []

    if request.method == "POST":
        form = await request.form
        action = form["action"]

        if action == "custom words":
            # Save custom words
            custom_words_text = form["custom_words"]
            custom_words_path.write_text(custom_words_text)
            await do_retrain()
        elif action == "pronounce":
            # Speak or guess pronunciation
            word = form["word"]
            if len(word) > 0:
                # Get multiple guesses
                result = voice2json("pronounce-word", "--quiet", "--nbest", "3", word)
                for line in result:
                    phonemes = re.split(r"\s+", line.strip(), maxsplit=1)[1]
                    guesses.append(phonemes)

    # Load custom words
    custom_words_text = custom_words_path.read_text()

    return await render_template(
        "words.html",
        profile=profile,
        pydash=pydash,
        custom_words=custom_words_text,
        word=word,
        guesses=guesses,
        len=len,
    )


@app.route("/phonemes")
async def phonemes():
    # Load word examples for each phoneme
    phoneme_examples_path = Path(
        pydash.get(profile, "speech-to-text.phoneme-examples-file")
    )

    phoneme_examples = {}
    with open(phoneme_examples_path, "r") as phoneme_examples_file:
        for line in phoneme_examples_file:
            line = line.strip()
            if len(line) == 0 or line.startswith("#"):
                continue

            phoneme, word, pronunciation = re.split(r"\s+", line, maxsplit=2)
            phoneme_examples[phoneme] = (word, pronunciation)

    return await render_template(
        "phonemes.html",
        profile=profile,
        pydash=pydash,
        sorted=sorted,
        phoneme_examples=phoneme_examples,
    )


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


async def do_retrain():
    """Re-trains voice2json profile and flashes warnings for unknown words."""
    # Re-train
    start_time = time.time()
    client.publish(TOPIC_TRAIN, "{}")
    result = await mqtt_train_queue.get()
    train_seconds = time.time() - start_time
    await flash(f"Re-trained in {train_seconds:0.2f} second(s)", "success")

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
        await flash("\n".join(warn_lines), "warning")


def stream_wav(topic: str, wav_data: bytes, chunk_size: int = chunk_size):
    """Streams a WAV file over MQTT in chunks."""
    # Convert to 16-bit 16Khz mono
    wav_data = maybe_convert_wav({}, wav_data)
    audio_data = wav_to_buffer(wav_data)

    # Split into chunks
    while len(audio_data) > 0:
        raw_chunk = audio_data[:chunk_size]

        # Re-wrap in WAV structure
        wav_chunk = buffer_to_wav(raw_chunk)
        client.publish(topic, wav_chunk)

        # Next chunk
        audio_data = audio_data[chunk_size:]

    # Send termination message
    client.publish(topic, None)


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true", help="Enable DEBUG mode")
    parser.add_argument(
        "--http-port", type=int, default=5000, help="Web server port (default: 5000)"
    )
    parser.add_argument(
        "--http-host", default="127.0.0.1", help="Web server host (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--mqtt-host", default="localhost", help="MQTT host (default: localhost)"
    )
    parser.add_argument(
        "--mqtt-port", type=int, default=1883, help="MQTT port (default: 1883)"
    )
    parser.add_argument("--profile", help="Path to voice2json profile")
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    logger.debug(args)

    if args.profile is not None:
        profile_path = Path(args.profile)

    # Get profile as JSON from voice2json
    profile = json.load(voice2json("print-profile"))

    client = mqtt.Client()

    def on_connect(client, userdata, flags, rc):
        try:
            logger.info("Connected")
            for topic in sub_topics:
                client.subscribe(topic)
                logger.debug(f"Subcribed to {topic}")
        except Exception as e:
            logging.exception("on_connect")

    def on_disconnect(client, userdata, flags, rc):
        try:
            # Automatically reconnect
            logger.info("Disconnected. Trying to reconnect...")
            client.reconnect()
        except Exception as e:
            logging.exception("on_disconnect")

    def on_message(client, userdata, msg):
        logger.debug(msg.topic)
        try:
            if msg.topic == TOPIC_TRANSCRIPTION:
                # Received transcription event
                mqtt_transcription = json.loads(msg.payload)
                loop.call_soon_threadsafe(
                    mqtt_transcription_queue.put_nowait, mqtt_transcription
                )
            elif msg.topic == TOPIC_INTENT:
                # Received recognize intent
                mqtt_intent = json.loads(msg.payload)
                loop.call_soon_threadsafe(mqtt_intent_queue.put_nowait, mqtt_intent)
            elif msg.topic == TOPIC_TRAINED:
                # Received trained intent
                loop.call_soon_threadsafe(mqtt_train_queue.put_nowait, msg.payload.decode())
        except Exception as e:
            logger.exception("on_message")

    # Connect to MQTT
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.connect(args.mqtt_host, args.mqtt_port)

    client.loop_start()

    # Start web server
    try:
        app.run(port=args.http_port, host=args.http_host, debug=args.debug)
    except KeyboardInterrupt:
        pass
