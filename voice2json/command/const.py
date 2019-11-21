"""
Data structures for voice command recording.
"""
from abc import ABC, abstractmethod
from enum import Enum
from typing import BinaryIO, Optional, List

import attr


class VoiceCommandResult(str, Enum):
    """Success/failure of voice command recognition."""

    SUCCESS = "success"
    FAILURE = "failure"


class VoiceCommandEventType(str, Enum):
    """Possible event types during voice command recognition."""

    STARTED = "started"
    SPEECH = "speech"
    SILENCE = "silence"
    STOPPED = "stopped"


@attr.s
class VoiceCommandEvent:
    """Speech/silence events."""

    type: VoiceCommandEventType = attr.ib()
    time: float = attr.ib()


@attr.s
class VoiceCommand:
    """Result of voice command recognition."""

    result: VoiceCommandResult = attr.ib()
    audio_data: Optional[bytes] = attr.ib(default=None)
    events: List[VoiceCommandEvent] = attr.ib(default=[])


class VoiceCommandRecorder(ABC):
    """Segment audio into voice command."""

    @abstractmethod
    def record(self, audio_source: BinaryIO) -> VoiceCommand:
        """Record voice command from audio stream."""
        pass
