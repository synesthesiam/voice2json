"""
Data structures for voice command recording.
"""
from abc import ABC, abstractmethod
from enum import Enum
from typing import BinaryIO, Optional

import attr


class VoiceCommandResult(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"


@attr.s
class VoiceCommandEvent:
    name: str = attr.ib()
    time: float = attr.ib()
    value: Optional[str] = attr.ib(default=None)


@attr.s
class VoiceCommand:
    result: VoiceCommandResult = attr.ib()
    wav_bytes: Optional[bytes] = attr.ib(default=None)
    events: List[VoiceCommandEvent] = attr.ib(default=[])


class VoiceCommandRecorder(ABC):
    """Segment audio into voice command."""

    @abstractmethod
    def record(self, audio_source: BinaryIO) -> VoiceCommand:
        """Record voice command from audio stream."""
        pass
