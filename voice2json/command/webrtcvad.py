#!/usr/bin/env python3
import logging

logger = logging.getLogger("webrtcvad")

import sys
import argparse
import math
import threading
import time
from collections import deque
from queue import Queue
from typing import List, BinaryIO, TextIO, Optional

import webrtcvad


def wait_for_command(
    audio_file: BinaryIO,
    vad_mode=3,
    sample_rate=16000,
    chunk_size=960,
    min_seconds=2,
    max_seconds=30,
    speech_seconds=0.3,
    silence_seconds=0.5,
    before_seconds=0.25,
) -> bytes:
    # Verify settings
    sample_rate = 16000
    assert vad_mode in range(1, 4), f"VAD mode must be 1-3 (got {vad_mode})"

    chunk_ms = 1000 * ((chunk_size / 2) / sample_rate)
    assert chunk_ms in [10, 20, 30], (
        "Sample rate and chunk size must make for 10, 20, or 30 ms buffer sizes,"
        + f" assuming 16-bit mono audio (got {chunk_ms} ms)"
    )

    # Voice detector
    vad = webrtcvad.Vad()
    vad.set_mode(vad_mode)

    seconds_per_buffer = chunk_size / sample_rate

    audio_chunks = Queue()

    # Store some number of seconds of audio data immediately before voice command starts
    before_buffers = int(math.ceil(before_seconds / seconds_per_buffer))
    before_phrase_chunks = deque(maxlen=before_buffers)

    # Store audio data during voice command
    phrase_buffer = bytes()
    report_audio = False

    # Pre-compute values
    speech_buffers = int(math.ceil(speech_seconds / seconds_per_buffer))

    # Processes one voice command
    def process_audio():
        nonlocal audio_chunks, phrase_buffer

        # State
        max_buffers = int(math.ceil(max_seconds / seconds_per_buffer))
        min_phrase_buffers = int(math.ceil(min_seconds / seconds_per_buffer))

        speech_buffers_left = speech_buffers
        is_speech = False
        last_speech = False
        in_phrase = False
        after_phrase = False

        finished = False
        timeout = False

        current_seconds = 0

        while True:
            chunk = audio_chunks.get()
            if in_phrase:
                phrase_buffer += chunk
            else:
                before_phrase_chunks.append(chunk)

            current_seconds += seconds_per_buffer

            # Check maximum number of seconds to record
            max_buffers -= 1
            if max_buffers <= 0:
                # Timeout
                logger.warn("Timeout")
                break

            # Detect speech in chunk
            is_speech = vad.is_speech(chunk, sample_rate)
            if is_speech and not last_speech:
                # Silence -> speech
                logger.debug(f"Speech at {current_seconds} second(s)")
            elif not is_speech and last_speech:
                # Speech -> silence
                logger.debug(f"Silence at {current_seconds} second(s)")

            last_speech = is_speech

            # Handle state changes
            if is_speech and speech_buffers_left > 0:
                speech_buffers_left -= 1
            elif is_speech and not in_phrase:
                # Start of phrase
                logger.debug(f"Command started at {current_seconds} second(s)")
                in_phrase = True
                after_phrase = False
                min_phrase_buffers = int(math.ceil(min_seconds / seconds_per_buffer))
            elif in_phrase and (min_phrase_buffers > 0):
                # In phrase, before minimum seconds
                min_phrase_buffers -= 1
            elif not is_speech:
                # Outside of speech
                if not in_phrase:
                    # Reset
                    speech_buffers_left = speech_buffers
                elif after_phrase and (silence_buffers > 0):
                    # After phrase, before stop
                    silence_buffers -= 1
                elif after_phrase and (silence_buffers <= 0):
                    # Phrase complete
                    logger.debug(f"Command finished at {current_seconds} second(s)")
                    break
                elif in_phrase and (min_phrase_buffers <= 0):
                    # Transition to after phrase
                    after_phrase = True
                    silence_buffers = int(
                        math.ceil(silence_seconds / seconds_per_buffer)
                    )

    # -------------------------------------------------------------------------

    def read_audio():
        nonlocal audio_file, audio_chunks, report_audio
        try:
            while True:
                chunk = audio_file.read(chunk_size)
                if len(chunk) == chunk_size:
                    if report_audio:
                        logger.debug("Receiving audio")
                        report_audio = False

                    audio_chunks.put(chunk)
                else:
                    # Avoid 100% CPU usage
                    time.sleep(0.01)
        except Exception as e:
            logger.exception("read_audio")

    threading.Thread(target=read_audio, daemon=True).start()

    # -------------------------------------------------------------------------

    # Process a voice command immediately
    chunk = audio_file.read(chunk_size)
    while len(chunk) == chunk_size:
        audio_chunks.put(chunk)
        process_audio()
        chunk = audio_file.read(chunk_size)

    # Merge before/during command audio data
    before_buffer = bytes()
    for chunk in before_phrase_chunks:
        before_buffer += chunk

    return before_buffer + phrase_buffer
