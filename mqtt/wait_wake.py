#!/usr/bin/env python3
import sys
import json
import argparse
import subprocess
import threading
import shlex
import logging

logger = logging.getLogger("wait_wake")

import paho.mqtt.client as mqtt

TOPIC_AUDIO_IN = "voice2json/wait-wake/audio-in"
TOPIC_DETECTED = "voice2json/wait-wake/detected"

from .utils import voice2json, maybe_convert_wav, wav_to_buffer


def main():
    parser = argparse.ArgumentParser(prog="wait_wake")
    parser.add_argument(
        "--host", default="localhost", help="MQTT host (default: localhost)"
    )
    parser.add_argument(
        "--port", type=int, default=1883, help="MQTT port (default: 1883)"
    )
    parser.add_argument("--profile", help="Path to voice2json profile")
    parser.add_argument(
        "--topic-detected",
        action="append",
        default=[TOPIC_DETECTED],
        help="Topic(s) to send detections out on",
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

    # Start wait-wake
    wait_wake_proc = voice2json(
        "wait-wake",
        "--audio-source",
        "-",
        *other_args,
        profile_path=args.profile,
        stream=True,
        text=False,
    )

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

        # True if audio has not yet been received
        first_audio = True

        def on_message(client, userdata, msg):
            nonlocal first_audio

            try:
                if msg.topic == TOPIC_AUDIO_IN:
                    # Skip termination message
                    if len(msg.payload) == 0:
                        return

                    if first_audio:
                        logger.debug("Receiving audio")
                        first_audio = False

                    wav_data = maybe_convert_wav(profile, msg.payload)
                    audio_data = wav_to_buffer(wav_data)

                    # Send to wait-wake
                    wait_wake_proc.stdin.write(audio_data)
                    wait_wake_proc.stdin.flush()
            except Exception as e:
                logger.exception("on_message")

        # Set up read thread
        def read_proc():
            try:
                for line in wait_wake_proc.stdout:
                    line = line.decode().strip()
                    print(line)
                    for topic in args.topic_detected:
                        client.publish(topic, line)
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
        wait_wake_proc.terminate()
        wait_wake_proc.wait()


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
