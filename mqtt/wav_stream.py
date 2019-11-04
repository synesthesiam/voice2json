#!/usr/bin/env python3
import sys
import argparse
import logging

logger = logging.getLogger("wav_stream")

import paho.mqtt.client as mqtt

from .utils import maybe_convert_wav, wav_to_buffer, buffer_to_wav


def main():
    parser = argparse.ArgumentParser(prog="wav_stream")
    parser.add_argument(
        "wav_file", nargs="*", default=[], help="Path(s) to WAV file(s)"
    )
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
        help="Number of bytes to send at a time (default: 960)",
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

        def send_wav(wav_data: bytes):
            # Convert to 16-bit 16Khz mono
            wav_data = maybe_convert_wav({}, wav_data)
            audio_data = wav_to_buffer(wav_data)

            # Split into chunks
            while len(audio_data) > 0:
                raw_chunk = audio_data[: args.chunk_size]

                # Re-wrap in WAV structure
                wav_chunk = buffer_to_wav(raw_chunk)
                for topic in args.topic:
                    client.publish(topic, wav_chunk)

                # Next chunk
                audio_data = audio_data[args.chunk_size :]


            # Send termination message
            for topic in args.topic:
                client.publish(topic, None)

        if len(args.wav_file) == 0:
            # Entire STDIN is WAV
            send_wav(sys.stdin.buffer.read())
        else:
            # Arguments are WAV paths
            for wav_path in args.wav_file:
                logger.debug(wav_path)
                with open(wav_path, "r") as wav_file:
                    send_wav(wav_file.read())

    except KeyboardInterrupt:
        pass
    finally:
        logger.debug("Shutting down")
        client.loop_stop()


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
