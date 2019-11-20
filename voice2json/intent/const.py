"""
Data structures for intent recognition.
"""
from abc import abstractmethod, ABC
from enum import Enum
from typing import List, Optional

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
    entities: List[Entity] = attr.ib(default=[])


@attr.s
class TagInfo:
    """Information used to process FST tags."""

    tag: str = attr.ib()
    start_index: int = attr.ib(default=0)
    raw_start_index: int = attr.ib(default=0)
    symbols: List[str] = attr.ib(default=[])
    raw_symbols: List[str] = attr.ib(default=[])


class RecognitionResult(str, Enum):
    """Result of a recognition."""

    SUCCESS = "success"
    FAILURE = "failure"


@attr.s
class Recognition:
    """Output of intent recognition."""

    result: RecognitionResult = attr.ib()
    intent: Optional[Intent] = attr.ib(default=None)
    text: str = attr.ib(default="")
    raw_text: str = attr.ib(default="")
    confidence: float = attr.ib(default=0)
    recognize_seconds: float = attr.ib(default=0)
    tokens: List[str] = attr.ib(default=[])
    raw_tokens: List[str] = attr.ib(default=[])


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
