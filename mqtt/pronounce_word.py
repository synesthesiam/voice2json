#!/usr/bin/env python3
import re
import sys
import json
import argparse
import subprocess
import threading
import shlex
import time
import logging

logger = logging.getLogger("pronounce_word")

import paho.mqtt.client as mqtt

TOPIC_PRONOUNCE = "voice2json/pronounce-word/pronounce"
TOPIC_PRONUNCIATIONS = "voice2json/pronounce-word/pronunciations"
TOPIC_TRAINED = "voice2json/train-profile/trained"

from .utils import voice2json


def main():
    parser = argparse.ArgumentParser(prog="pronounce_word")
    parser.add_argument(
        "--host", default="localhost", help="MQTT host (default: localhost)"
    )
    parser.add_argument(
        "--port", type=int, default=1883, help="MQTT port (default: 1883)"
    )
    parser.add_argument("--profile", help="Path to voice2json profile")
    parser.add_argument(
        "--topic-pronunciations",
        action="append",
        default=[TOPIC_PRONUNCIATIONS],
        help="Topic(s) to send word pronunciations out on",
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

    pronounce_word_proc = voice2json(
        "pronounce-word",
        "--quiet",
        "--newline",
        *other_args,
        profile_path=args.profile,
        stream=True,
    )
    read_thread = None

    try:
        # Listen for messages
        client = mqtt.Client()

        def on_connect(client, userdata, flags, rc):
            try:
                logger.info("Connected")

                # Subscribe to topics
                for topic in [TOPIC_PRONOUNCE, TOPIC_TRAINED]:
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

        # Set up read thread
        read_ready_event = threading.Event()

        def read_proc(proc):
            try:
                while True:
                    read_ready_event.wait()
                    read_ready_event.clear()

                    word = ""
                    pronunciations = []
                    for line in pronounce_word_proc.stdout:
                        line = line.strip()
                        print(line)

                        if len(line) == 0:
                            payload = json.dumps(
                                {"word": word, "pronunciations": pronunciations}
                            )

                            for topic in args.topic_pronunciations:
                                client.publish(topic, payload)

                            # Reset
                            word = ""
                            pronunciations = []
                        else:
                            word, phonemes = re.split(r"\s+", line, maxsplit=1)
                            pronunciations.append(phonemes)
            except ValueError:
                # Expected when restarting
                pass
            except Exception as e:
                logger.exception("read_proc")

        def restart():
            nonlocal pronounce_word_proc, read_thread

            try:
                if pronounce_word_proc is not None:
                    pronounce_word_proc.terminate()

                    # Properly closes stdout
                    pronounce_word_proc.communicate()
                    pronounce_word_proc = None

                if read_thread is not None:
                    read_ready_event.set()
                    read_thread.join()
                    read_thread = None

                # Start transcribe-wav
                pronounce_word_proc = voice2json(
                    "transcribe-wav",
                    "--input-size",
                    *other_args,
                    profile_path=args.profile,
                    stream=True,
                    text=False,
                )

                read_thread = threading.Thread(
                    target=read_proc, daemon=True, args=(pronounce_word_proc,)
                )

                read_thread.start()
                read_ready_event.set()
            except Exception as e:
                logger.exception("restart")

        # Initial startup
        restart()

        def on_message(client, userdata, msg):
            try:
                if msg.topic == TOPIC_PRONOUNCE:
                    line = msg.payload.decode().strip()
                    print(line)
                    pronounce_word_proc.stdin.write(line + "\n")
                    pronounce_word_proc.stdin.flush()
                elif msg.topic == TOPIC_TRAINED:
                    logger.info("Reloading pronounce-word")
                    restart()
            except Exception as e:
                logger.exception("on_message")

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
        pronounce_word_proc.terminate()
        pronounce_word_proc.wait()


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
