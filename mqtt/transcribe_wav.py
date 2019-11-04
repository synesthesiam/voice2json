#!/usr/bin/env python3
import sys
import json
import argparse
import subprocess
import threading
import shlex
import time
import logging

logger = logging.getLogger("transcribe_wav")

import paho.mqtt.client as mqtt

TOPIC_AUDIO_IN = "voice2json/transcribe-wav/audio-in"
TOPIC_TRANSCRIPTION = "voice2json/transcribe-wav/transcription"
TOPIC_TRAINED = "voice2json/train-profile/trained"

from .utils import voice2json, maybe_convert_wav, wav_to_buffer, buffer_to_wav


def main():
    parser = argparse.ArgumentParser(prog="transcribe_wav")
    parser.add_argument(
        "--host", default="localhost", help="MQTT host (default: localhost)"
    )
    parser.add_argument(
        "--port", type=int, default=1883, help="MQTT port (default: 1883)"
    )
    parser.add_argument("--profile", help="Path to voice2json profile")
    parser.add_argument(
        "--topic-transcription",
        action="append",
        default=[TOPIC_TRANSCRIPTION],
        help="Topic(s) to send transcriptions out on",
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

    transcribe_wav_proc = None
    read_thread = None

    try:
        # Listen for messages
        client = mqtt.Client()

        def on_connect(client, userdata, flags, rc):
            try:
                logger.info("Connected")

                # Subscribe to topics
                for topic in [TOPIC_AUDIO_IN, TOPIC_TRAINED]:
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

        # Buffer with current voice command.
        # Any empty audio-in message forces a transcription.
        audio_data = bytes()

        # Set up read thread
        def read_proc(proc):
            try:
                while True:
                    for line in proc.stdout:
                        line = line.decode().strip()
                        print(line)
                        for topic in args.topic_transcription:
                            client.publish(topic, line)
            except ValueError:
                # Expected when restarting
                pass
            except Exception as e:
                logger.exception("read_proc")

        def restart():
            nonlocal transcribe_wav_proc, read_thread, first_audio, audio_data

            try:
                if transcribe_wav_proc is not None:
                    transcribe_wav_proc.terminate()

                    # Properly closes stdout
                    transcribe_wav_proc.communicate()
                    transcribe_wav_proc = None

                if read_thread is not None:
                    read_thread.join()
                    read_thread = None

                # Reset state
                first_audio = True
                audio_data = bytes()

                # Start transcribe-wav
                transcribe_wav_proc = voice2json(
                    "transcribe-wav",
                    "--input-size",
                    *other_args,
                    profile_path=args.profile,
                    stream=True,
                    text=False,
                )

                read_thread = threading.Thread(
                    target=read_proc, daemon=True, args=(transcribe_wav_proc,)
                )

                read_thread.start()
            except Exception as e:
                logger.exception("restart")

        # Initial startup
        restart()

        def on_message(client, userdata, msg):
            nonlocal first_audio, audio_data

            try:
                if msg.topic == TOPIC_AUDIO_IN:
                    if first_audio:
                        logger.debug("Receiving audio")
                        first_audio = False
                        audio_data = bytes()

                    if len(msg.payload) == 0:
                        # Do transcription
                        wav_data = buffer_to_wav(audio_data)
                        size_str = str(len(wav_data)) + "\n"

                        # Send to transcribe-wav
                        transcribe_wav_proc.stdin.write(size_str.encode())
                        transcribe_wav_proc.stdin.write(wav_data)
                        transcribe_wav_proc.stdin.flush()

                        first_audio = True
                    else:
                        # Add to buffer
                        wav_data = maybe_convert_wav(profile, msg.payload)
                        audio_data += wav_to_buffer(wav_data)
                elif msg.topic == TOPIC_TRAINED:
                    logger.info("Reloading transcribe-wav")
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
        transcribe_wav_proc.terminate()
        transcribe_wav_proc.wait()


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
