"""
Data structures for intent recognition.
"""
from abc import abstractmethod, ABC
from enum import Enum
from typing import List, Optional, Dict, Any

import attr
import pywrapfst as fst


@attr.s
class Entity:
    """Named entity from intent."""

    entity: str = attr.ib()
    value: str = attr.ib()
    raw_value: str = attr.ib(default="")
    start: int = attr.ib(default=0)
    raw_start: int = attr.ib(default=0)
    end: int = attr.ib(default=0)
    raw_end: int = attr.ib(default=0)


@attr.s
class Intent:
    """Named intention with entities and slots."""

    name: str = attr.ib()
    confidence: float = attr.ib(default=0)

    @classmethod
    def fromdict(cls, d: Dict[str, Any]) -> "Intent":
        """Load Intent from a dictionary."""
        kwargs = {}

        for field in ["name", "confidence"]:
            if field in d:
                kwargs[field] = d[field]

        return Intent(**kwargs)


@attr.s
class TagInfo:
    """Information used to process FST tags."""

    tag: str = attr.ib()
    start_index: int = attr.ib(default=0)
    raw_start_index: int = attr.ib(default=0)
    symbols: List[str] = attr.ib(factory=list)
    raw_symbols: List[str] = attr.ib(factory=list)


class RecognitionResult(str, Enum):
    """Result of a recognition."""

    SUCCESS = "success"
    FAILURE = "failure"


@attr.s
class Recognition:
    """Output of intent recognition."""

    result: RecognitionResult = attr.ib()
    intent: Optional[Intent] = attr.ib(default=None)
    entities: List[Entity] = attr.ib(factory=list)
    text: str = attr.ib(default="")
    raw_text: str = attr.ib(default="")
    recognize_seconds: float = attr.ib(default=0)
    tokens: List[str] = attr.ib(factory=list)
    raw_tokens: List[str] = attr.ib(factory=list)

    # Transcription fields
    likelihood: float = attr.ib(default=0)
    wav_seconds: float = attr.ib(default=0)
    transcribe_seconds: float = attr.ib(default=0)

    @classmethod
    def fromdict(cls, d: Dict[str, Any]) -> "Recognition":
        """Load Recognition from a dictionary."""
        kwargs = {"result": RecognitionResult.SUCCESS}

        for field in [
            "text",
            "raw_text",
            "recognize_seconds",
            "tokens",
            "raw_tokens",
            "likelihood",
            "wav_seconds",
            "transcribe_seconds",
        ]:
            if field in d:
                kwargs[field] = d[field]

        if "intent" in d:
            kwargs["intent"] = Intent.fromdict(d["intent"])

        if "entities" in d:
            kwargs["entities"] = [Entity(**e) for e in d["entities"]]

        return Recognition(**kwargs)


class Recognizer(ABC):
    """Base class of intent recognizers."""

    @abstractmethod
    def recognize(self, tokens: List[str]) -> Recognition:
        """Recognize intent from text."""
        pass

    @property
    @abstractmethod
    def intent_fst(self) -> fst.Fst:
        """Get intent finite state transducer."""
        pass
