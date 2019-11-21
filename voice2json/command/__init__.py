"""Voice command recording support."""
import asyncio
import logging
import sys
import argparse
import math
import threading
import time
from collections import deque
from queue import Queue
from typing import List, BinaryIO, TextIO, Optional

import webrtcvad

from voice2json.command.const import (
    VoiceCommandRecorder,
    VoiceCommand,
    VoiceCommandResult,
    VoiceCommandEvent,
    VoiceCommandEventType,
)

_LOGGER = logging.getLogger(__name__)

# -----------------------------------------------------------------------------


class WebRtcVadRecorder(VoiceCommandRecorder):
    """Detect speech/silence using webrtcvad."""

    def __init__(
        self,
        vad_mode: int = 3,
        sample_rate: int = 16000,
        chunk_size: int = 960,
        min_seconds: float = 2,
        max_seconds: float = 30,
        speech_seconds: float = 0.3,
        silence_seconds: float = 0.5,
        before_seconds: float = 0.25,
    ):
        self.vad_mode = vad_mode
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.min_seconds = min_seconds
        self.max_seconds = max_seconds
        self.speech_seconds = speech_seconds
        self.silence_seconds = silence_seconds
        self.before_seconds = before_seconds

        # Verify settings
        assert self.vad_mode in range(1, 4), f"VAD mode must be 1-3 (got {vad_mode})"

        chunk_ms = 1000 * ((self.chunk_size / 2) / self.sample_rate)
        assert chunk_ms in [10, 20, 30], (
            "Sample rate and chunk size must make for 10, 20, or 30 ms buffer sizes,"
            + f" assuming 16-bit mono audio (got {chunk_ms} ms)"
        )

        # Voice detector
        self.vad = webrtcvad.Vad()
        self.vad.set_mode(self.vad_mode)

        self.seconds_per_buffer = self.chunk_size / self.sample_rate

        # Store some number of seconds of audio data immediately before voice command starts
        self.before_buffers = int(
            math.ceil(self.before_seconds / self.seconds_per_buffer)
        )

        # Pre-compute values
        self.speech_buffers = int(
            math.ceil(self.speech_seconds / self.seconds_per_buffer)
        )

    async def record(self, audio_source: BinaryIO) -> VoiceCommand:
        """Record voice command from audio stream."""

        async def async_chunks():
            while True:
                chunk = audio_source.read(self.chunk_size)
                if chunk:
                    if len(chunk) == self.chunk_size:
                        yield chunk
                    else:
                        # Avoid 100% CPU
                        asyncio.sleep(0.01)
                else:
                    break

        # State
        events: List[VoiceCommandEvent] = []
        before_phrase_chunks: int = deque(maxlen=self.before_buffers)
        phrase_buffer: bytes = bytes()
        report_audio: bool = False

        max_buffers: int = int(math.ceil(self.max_seconds / self.seconds_per_buffer))
        min_phrase_buffers: int = int(
            math.ceil(self.min_seconds / self.seconds_per_buffer)
        )

        speech_buffers_left: int = self.speech_buffers
        is_speech: bool = False
        last_speech: bool = False
        in_phrase: bool = False
        after_phrase: bool = False

        current_seconds: float = 0

        # Process audio chunks
        async for chunk in async_chunks():
            if report_audio:
                _LOGGER.debug("Receiving audio")
                report_audio = False

            if in_phrase:
                phrase_buffer += chunk
            else:
                before_phrase_chunks.append(chunk)

            current_seconds += self.seconds_per_buffer

            # Check maximum number of seconds to record
            max_buffers -= 1
            if max_buffers <= 0:
                # Timeout
                _LOGGER.warning("Voice command timeout")
                return VoiceCommand(result=VoiceCommandResult.FAILURE, events=events)

            # Detect speech in chunk
            is_speech = self.vad.is_speech(chunk, self.sample_rate)
            if is_speech and not last_speech:
                # Silence -> speech
                events.append(
                    VoiceCommandEvent(
                        type=VoiceCommandEventType.SPEECH, time=current_seconds
                    )
                )
                pass
            elif not is_speech and last_speech:
                # Speech -> silence
                events.append(
                    VoiceCommandEvent(
                        type=VoiceCommandEventType.SILENCE, time=current_seconds
                    )
                )
                pass

            last_speech = is_speech

            # Handle state changes
            if is_speech and speech_buffers_left > 0:
                speech_buffers_left -= 1
            elif is_speech and not in_phrase:
                # Start of phrase
                events.append(
                    VoiceCommandEvent(
                        type=VoiceCommandEventType.STARTED, time=current_seconds
                    )
                )
                in_phrase = True
                after_phrase = False
                min_phrase_buffers = int(
                    math.ceil(self.min_seconds / self.seconds_per_buffer)
                )
            elif in_phrase and (min_phrase_buffers > 0):
                # In phrase, before minimum seconds
                min_phrase_buffers -= 1
            elif not is_speech:
                # Outside of speech
                if not in_phrase:
                    # Reset
                    speech_buffers_left = self.speech_buffers
                elif after_phrase and (silence_buffers > 0):
                    # After phrase, before stop
                    silence_buffers -= 1
                elif after_phrase and (silence_buffers <= 0):
                    # Phrase complete
                    events.append(
                        VoiceCommandEvent(
                            type=VoiceCommandEventType.STOPPED, time=current_seconds
                        )
                    )
                    break
                elif in_phrase and (min_phrase_buffers <= 0):
                    # Transition to after phrase
                    after_phrase = True
                    silence_buffers = int(
                        math.ceil(self.silence_seconds / self.seconds_per_buffer)
                    )

        # -------------------------------------------------------------------------

        # Merge before/during command audio data
        before_buffer = bytes()
        for chunk in before_phrase_chunks:
            before_buffer += chunk

        return VoiceCommand(
            result=VoiceCommandResult.SUCCESS,
            audio_data=before_buffer + phrase_buffer,
            events=events,
        )
