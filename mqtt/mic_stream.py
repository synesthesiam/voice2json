#!/usr/bin/env python3
import sys
import argparse
import logging

logger = logging.getLogger("mic_stream")

import paho.mqtt.client as mqtt

from .utils import buffer_to_wav

def main():
    parser = argparse.ArgumentParser(prog="mic_stream")
    parser.add_argument(
        "--host", default="localhost", help="MQTT host (default: localhost)"
    )
    parser.add_argument(
        "--port", type=int, default=1883, help="MQTT port (default: 1883)"
    )
    parser.add_argument(
        "--topic", action="append", required=True, help="Topic(s) to send audio to"
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=960,
        help="Number of bytes to read/send at a time (default: 960)",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG messages to the console"
    )
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    logger.debug(args)

    # Listen for messages
    client = mqtt.Client()

    try:

        def on_connect(client, userdata, flags, rc):
            try:
                logger.info("Connected")
            except Exception as e:
                logging.exception("on_connect")

        def on_disconnect(client, userdata, flags, rc):
            try:
                # Automatically reconnect
                logger.info("Disconnected. Trying to reconnect...")
                client.reconnect()
            except Exception as e:
                logging.exception("on_disconnect")

        # Connect
        client.on_connect = on_connect
        client.on_disconnect = on_disconnect
        client.connect(args.host, args.port)

        client.loop_start()

        while True:
            chunk = sys.stdin.buffer.read(args.chunk_size)

            # Assume 16-bit 16Khz mono
            wav_data = buffer_to_wav({}, chunk)

            for topic in args.topic:
                client.publish(topic, wav_data)

    except KeyboardInterrupt:
        pass
    finally:
        logger.debug("Shutting down")
        client.loop_stop()


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
