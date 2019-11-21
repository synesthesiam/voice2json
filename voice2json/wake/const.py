"""
Data structures for wake/hot word detection.
"""
from abc import ABC, abstractmethod
from typing import BinaryIO, Iterable

import attr


@attr.s
class WakeWordDetection:
    """Result of wake word detection."""

    keyword: str = attr.ib()
    time: float = attr.ib()


class WakeWordDetector(ABC):
    """Base class for wake word detectors."""

    @abstractmethod
    def detect(self, audio_source: BinaryIO) -> Iterable[WakeWordDetection]:
        """Detect wake word in audio stream."""
        pass
