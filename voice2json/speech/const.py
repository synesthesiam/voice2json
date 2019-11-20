"""
Data structures for speech to text.
"""
from abc import ABC, abstractmethod
from enum import Enum

import attr


class TranscriptionResult(str, Enum):
    """Result of a transcription."""

    SUCCESS = "success"
    FAILURE = "failure"


@attr.s
class Transcription:
    """Output of speech to text."""

    result: TranscriptionResult = attr.ib()
    text: str = attr.ib(default="")
    likelihood: float = attr.ib(default=0)
    transcribe_seconds: float = attr.ib(default=0)
    wav_seconds: float = attr.ib(default=0)


class Transcriber(ABC):
    """Does speech to text on a WAV buffer."""

    @abstractmethod
    def transcribe_wav(self, wav_data: bytes) -> Transcription:
        """Speech to text."""
        pass

    @abstractmethod
    def stop(self):
        """Stop transcriber."""
        pass


class KaldiModelType(str, Enum):
    """Supported Kaldi model types."""

    NNET3 = "nnet3"
    GMM = "gmm"
