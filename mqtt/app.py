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
from quart import (
    Quart,
    request,
    render_template,
    send_from_directory,
    flash,
    send_file,
    jsonify,
)

from utils import voice2json, buffer_to_wav, maybe_convert_wav, wav_to_buffer

# -----------------------------------------------------------------------------

# MQTT topics
TOPIC_TRANSCRIBE_AUDIO_IN = "voice2json/transcribe-wav/audio-in"
TOPIC_TRANSCRIPTION = "voice2json/transcribe-wav/transcription"
TOPIC_RECOGNIZE = "voice2json/recognize-intent/recognize"
TOPIC_INTENT = "voice2json/recognize-intent/intent"
TOPIC_TRAIN = "voice2json/train-profile/train"
TOPIC_TRAINED = "voice2json/train-profile/trained"
TOPIC_WAKE_AUDIO_IN = "voice2json/wait-wake/audio-in"
TOPIC_DETECTED = "voice2json/wait-wake/detected"
TOPIC_COMMAND_AUDIO_IN = "voice2json/record-command/audio-in"
TOPIC_RECORDED = "voice2json/record-command/recorded"
sub_topics = [
    TOPIC_INTENT,
    TOPIC_TRANSCRIPTION,
    TOPIC_TRAINED,
    TOPIC_DETECTED,
    TOPIC_RECORDED,
]

profile_path: Optional[Path] = None
profile: Dict[str, Any] = {}
client = None
chunk_size = 960

# Quart application
app = Quart("voice2json", template_folder=Path("templates").absolute())
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
mqtt_wake_queue = asyncio.Queue()
mqtt_command_queue = asyncio.Queue()

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

                logger.info(f"Recorded {len(raw_audio_data)} byte(s)")
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

        # Automatically re-train
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
# Rhasspy API
# -----------------------------------------------------------------------------


@app.route("/api/speech-to-text", methods=["POST"])
async def api_speech_to_text():
    """WAV -> JSON with text"""
    wav_data = maybe_convert_wav(profile, await request.data)
    logger.debug(f"Transcribing {len(wav_data)} byte(s)")
    stream_wav(TOPIC_TRANSCRIBE_AUDIO_IN, wav_data)
    return jsonify(await mqtt_transcription_queue.get())


@app.route("/api/text-to-intent", methods=["POST"])
async def api_text_to_intent():
    """Text -> JSON with intent"""
    sentence = (await request.data).decode()
    logger.debug(f"Recognizing '{sentence}'")
    client.publish(TOPIC_RECOGNIZE, json.dumps({"text": sentence}))
    return jsonify(await mqtt_intent_queue.get())


@app.route("/api/sentences", methods=["GET", "POST"])
async def api_sentences():
    """Get or overwrite sentences.ini"""
    sentences_path = Path(pydash.get(profile, "training.sentences-file"))
    if request.method == "POST":
        sentences_text = (await request.data).decode()
        sentences_path.write_text(sentences_text)

        # Return length of written text
        return str(len(sentences_text))
    else:
        return sentences_path.read_text()


@app.route("/api/custom-words", methods=["GET", "POST"])
async def api_custom_words():
    """Get or overwrite custom_words.txt"""
    words_path = Path(pydash.get(profile, "training.custom-words-file"))
    if request.method == "POST":
        words_text = (await request.data).decode()
        words_path.write_text(words_text)

        # Return length of written text
        return str(len(words_text))
    else:
        return words_path.read_text()


@app.route("/api/slots", methods=["GET", "POST"])
async def api_slots():
    """Get or overwrite slots"""
    slots_dir = Path(pydash.get(profile, "training.slots-directory"))
    if request.method == "POST":
        slots_dict = await request.json
        slots_dir.mkdir(parents=True, exist_ok=True)

        # Write slots
        total_length = 0
        for slot_name, slot_values in slots_dict.items():
            slot_file_path = slots_dir / slot_name
            with open(slot_file_path, "w") as slot_file:
                for value in slot_values:
                    value = value.strip()
                    print(value, file=slot_file)
                    total_length += len(value)

        # Return length of written text
        return str(total_length)
    else:
        # Read slots into dictionary
        slots_dict = {}
        for slot_file_path in slots_dir.glob("*"):
            if slot_file_path.is_file():
                slot_name = slot_file_path.name
                slots_dict[slot_name] = [
                    line.strip() for line in slot_file_path.read_text().splitlines()
                ]

        return jsonify(slots_dict)


@app.route("/api/train", methods=["POST"])
async def api_train():
    """Re-train profile"""
    return await do_retrain(flash=False)


# -----------------------------------------------------------------------------
# Streams
# -----------------------------------------------------------------------------

last_transcription = ""

STATE_BEFORE_WAKE = 0
STATE_DETECT_SILENCE = 1


@app.route("/stream/wake-speech-to-text", methods=["GET", "POST"])
async def stream_wake_speech_to_text():
    """HTTP audio -> wait-wake -> record-command -> speech-to-text"""
    global last_transcription

    if request.method == "POST":
        last_transcription = ""

        state = STATE_BEFORE_WAKE
        async for audio_chunk in request.body:
            wav_chunk = buffer_to_wav(audio_chunk)

            if state == STATE_BEFORE_WAKE:
                client.publish(TOPIC_WAKE_AUDIO_IN, wav_chunk)

                try:
                    # Wake word detected
                    mqtt_wake_queue.get_nowait()
                    state = STATE_DETECT_SILENCE
                except asyncio.QueueEmpty:
                    pass
            elif state == STATE_DETECT_SILENCE:
                client.publish(TOPIC_COMMAND_AUDIO_IN, wav_chunk)

                try:
                    # Voice command recorded
                    mqtt_command_queue.get_nowait()
                    break
                except asyncio.QueueEmpty:
                    pass

        transcribe_result = await mqtt_transcription_queue.get()
        logger.debug(transcribe_result)

        last_transcription = transcribe_result.get("text", "")
        request.body.set_complete()
        return last_transcription
    else:
        return last_transcription


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


async def do_retrain(flash=True) -> str:
    """Re-trains voice2json profile and flashes warnings for unknown words."""
    start_time = time.time()
    client.publish(TOPIC_TRAIN, "{}")
    result = await mqtt_train_queue.get()
    train_seconds = time.time() - start_time

    if flash:
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

    warn_text = "\n".join(warn_lines) if warn_lines is not None else ""
    if flash and (warn_lines is not None):
        await flash(warn_text, "warning")

    return warn_text


def stream_wav(topic: str, wav_data: bytes, chunk_size: int = chunk_size):
    """Streams a WAV file over MQTT in chunks."""
    # Convert to 16-bit 16Khz mono
    wav_data = maybe_convert_wav(profile, wav_data)
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
                # Received training result
                loop.call_soon_threadsafe(
                    mqtt_train_queue.put_nowait, msg.payload.decode()
                )
            elif msg.topic == TOPIC_DETECTED:
                # Received wake word detection
                mqtt_detected = json.loads(msg.payload)
                loop.call_soon_threadsafe(mqtt_wake_queue.put_nowait, mqtt_detected)
            elif msg.topic == TOPIC_RECORDED:
                # Voice command recorded
                mqtt_recorded = json.loads(msg.payload)
                loop.call_soon_threadsafe(mqtt_command_queue.put_nowait, mqtt_recorded)
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
