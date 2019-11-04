#!/usr/bin/env python3
import sys
import json
import argparse
import subprocess
import threading
import shlex
import time
import logging

logger = logging.getLogger("record_command")

import paho.mqtt.client as mqtt

TOPIC_AUDIO_IN = "voice2json/record-command/audio-in"
TOPIC_AUDIO_OUT = "voice2json/record-command/audio-out"

from .utils import voice2json, maybe_convert_wav, wav_to_buffer, buffer_to_wav


def main():
    parser = argparse.ArgumentParser(prog="record_command")
    parser.add_argument(
        "--host", default="localhost", help="MQTT host (default: localhost)"
    )
    parser.add_argument(
        "--port", type=int, default=1883, help="MQTT port (default: 1883)"
    )
    parser.add_argument("--profile", help="Path to voice2json profile")
    parser.add_argument(
        "--topic-audio-out",
        action="append",
        default=[TOPIC_AUDIO_OUT],
        help="Topic(s) to send recorded audio out on",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=960,
        help="Number of audio bytes to send at a time",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG messages to the console"
    )
    args, other_args = parser.parse_known_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    logger.debug(args)

    # Load profile
    profile = json.load(voice2json("print-profile", profile_path=args.profile))
    logger.debug("Loaded profile")

    read_event = threading.Event()
    record_command_proc = None

    try:
        # Listen for messages
        client = mqtt.Client()

        def on_connect(client, userdata, flags, rc):
            try:
                logger.info("Connected")

                # Subscribe to topics
                for topic in [TOPIC_AUDIO_IN]:
                    client.subscribe(topic)
                    logger.debug(f"Subscribed to {topic}")
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
            nonlocal read_event, record_command_proc

            try:
                if msg.topic == TOPIC_AUDIO_IN:
                    # Skip termination message
                    if len(msg.payload) == 0:
                        return

                    if record_command_proc is None:
                        logger.debug("Receiving audio")

                        # Start record-command
                        record_command_proc = voice2json(
                            "record-command",
                            "--audio-source",
                            "-",
                            "--output-size",
                            *other_args,
                            profile_path=args.profile,
                            stream=True,
                            text=False,
                        )

                        read_event.set()

                    wav_data = maybe_convert_wav(profile, msg.payload)
                    audio_data = wav_to_buffer(wav_data)

                    # Send to record-command
                    record_command_proc.stdin.write(audio_data)
                    record_command_proc.stdin.flush()
            except Exception as e:
                logger.exception("on_message")

        # Set up read thread
        def read_proc():
            nonlocal read_event, record_command_proc

            try:
                while True:
                    read_event.wait()
                    read_event.clear()

                    # Size is output first on a separate line
                    line = record_command_proc.stdout.readline().decode().strip()
                    num_bytes = int(line)
                    audio_buffer = bytes()

                    # Followed by payload
                    while len(audio_buffer) < num_bytes:
                        audio_buffer += record_command_proc.stdout.read(
                            num_bytes - len(audio_buffer)
                        )

                    logger.debug(f"Sending audio ({len(audio_buffer)})")

                    # Split into chunks
                    while len(audio_buffer) > 0:
                        audio_chunk = audio_buffer[: args.chunk_size]
                        wav_chunk = buffer_to_wav(audio_chunk)

                        # Forward downstream
                        for topic in args.topic_audio_out:
                            client.publish(topic, wav_chunk)

                        audio_buffer = audio_buffer[args.chunk_size :]

                    # Send termination message
                    for topic in args.topic_audio_out:
                        client.publish(topic, None)

                    # Shutdown record-command
                    record_command_proc.terminate()
                    record_command_proc.wait()
                    record_command_proc = None

                    read_event.clear()
            except Exception as e:
                logger.exception("read_proc")

        threading.Thread(target=read_proc, daemon=True).start()

        # Connect
        client.on_connect = on_connect
        client.on_disconnect = on_disconnect
        client.on_message = on_message
        client.connect(args.host, args.port)

        client.loop_forever()
    except KeyboardInterrupt:
        pass
    finally:
        logger.debug("Shutting down")


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
