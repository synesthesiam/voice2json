#!/usr/bin/env python3
import sys
import json
import argparse
import subprocess
import threading
import shlex
import time
import logging

logger = logging.getLogger("recognize_intent")

import paho.mqtt.client as mqtt

TOPIC_RECOGNIZE = "voice2json/recognize-intent/recognize"
TOPIC_INTENT = "voice2json/recognize-intent/intent"
TOPIC_TRAINED = "voice2json/train-profile/trained"

from .utils import voice2json


def main():
    parser = argparse.ArgumentParser(prog="recognize_intent")
    parser.add_argument(
        "--host", default="localhost", help="MQTT host (default: localhost)"
    )
    parser.add_argument(
        "--port", type=int, default=1883, help="MQTT port (default: 1883)"
    )
    parser.add_argument("--profile", help="Path to voice2json profile")
    parser.add_argument(
        "--topic-intent",
        action="append",
        default=[TOPIC_INTENT],
        help="Topic(s) to send recognized intents out on",
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

    recognize_intent_proc = None
    read_thread = None

    try:
        # Listen for messages
        client = mqtt.Client()

        def on_connect(client, userdata, flags, rc):
            try:
                logger.info("Connected")

                # Subscribe to topics
                for topic in [TOPIC_RECOGNIZE, TOPIC_TRAINED]:
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

                    for line in proc.stdout:
                        line = line.strip()
                        print(line)
                        for topic in args.topic_intent:
                            client.publish(topic, line)
            except ValueError:
                # Expected when restarting
                pass
            except Exception as e:
                logger.exception("read_proc")

        def restart():
            nonlocal recognize_intent_proc, read_thread

            try:
                if recognize_intent_proc is not None:
                    recognize_intent_proc.terminate()

                    # Properly closes stdout
                    recognize_intent_proc.communicate()
                    recognize_intent_proc = None

                if read_thread is not None:
                    read_ready_event.set()
                    read_thread.join()
                    read_thread = None

                # Start recognize-intent
                recognize_intent_proc = voice2json(
                    "recognize-intent", *other_args, profile_path=args.profile, stream=True
                )

                read_thread = threading.Thread(
                    target=read_proc, daemon=True, args=(recognize_intent_proc,)
                )

                read_thread.start()
                read_ready_event.set()
            except Exception as e:
                logger.exception("restart")

        # Initial startup
        restart()

        def on_message(client, userdata, msg):
            nonlocal recognize_intent_proc

            try:
                logger.info(msg.topic)
                if msg.topic == TOPIC_RECOGNIZE:
                    line = msg.payload.decode().strip()
                    recognize_intent_proc.stdin.write(line + "\n")
                    recognize_intent_proc.stdin.flush()
                elif msg.topic == TOPIC_TRAINED:
                    logger.info("Reloading recognize-intent")
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
        recognize_intent_proc.terminate()
        recognize_intent_proc.wait()


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
