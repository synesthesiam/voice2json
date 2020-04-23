"""Utility methods for voice2json."""
import collections
import io
import logging
import os
import random
import sys
import typing
import wave
from collections import deque
from pathlib import Path

import jsonlines
import pydash

_LOGGER = logging.getLogger("voice2json.utils")
T = typing.TypeVar("T")

# -----------------------------------------------------------------------------


def get_wav_duration(wav_bytes: bytes) -> float:
    """Get the duration of a WAV file in seconds."""
    with io.BytesIO(wav_bytes) as wav_buffer:
        with wave.open(wav_buffer) as wav_file:
            frames = wav_file.getnframes()
            rate = wav_file.getframerate()
            return frames / float(rate)


# -----------------------------------------------------------------------------


def ppath(
    profile, profile_dir: Path, query: str, default: typing.Optional[str] = None
) -> typing.Optional[Path]:
    """Returns a Path from a profile or a default Path relative to the profile directory."""
    result = pydash.get(profile, query)
    if result is None:
        if default is not None:
            result = profile_dir / Path(default)
    else:
        result = Path(result)

    return result


# -----------------------------------------------------------------------------


def recursive_update(
    base_dict: typing.Dict[typing.Any, typing.Any],
    new_dict: typing.Mapping[typing.Any, typing.Any],
) -> None:
    """Recursively overwrites values in base dictionary with values from new dictionary"""
    for k, v in new_dict.items():
        if isinstance(v, collections.Mapping) and (k in base_dict):
            recursive_update(base_dict[k], v)
        else:
            base_dict[k] = v


# -----------------------------------------------------------------------------


def print_json(value: typing.Any, out_file=sys.stdout) -> None:
    """Print a single line of JSON to stdout."""
    with jsonlines.Writer(out_file) as out:
        # pylint: disable=E1101
        out.write(value)

    out_file.flush()


# -----------------------------------------------------------------------------


def env_constructor(loader, node):
    """Expand !env STRING to replace environment variables in STRING."""
    return os.path.expandvars(node.value)


# -----------------------------------------------------------------------------


def dag_paths_random(G, source: int, target: int) -> typing.Iterable[typing.List[int]]:
    """Yields paths from source to target in random order. Assumes no cycles."""
    q: typing.Deque[typing.Tuple[int, typing.List[int]]] = deque([(source, [])])
    while q:
        node, path = q.popleft()
        if node == target:
            yield path + [target]
        else:
            children = list(G[node])
            random.shuffle(children)
            for child in children:
                q.append((child, path + [node]))


def itershuffle(
    iterable: typing.Iterable[T], bufsize: int = 1000
) -> typing.Iterable[T]:
    """Shuffle an iterator by maintaining a buffer of elements.

    Original credit: https://gist.github.com/andres-erbsen/1307752
    """
    iterator = iter(iterable)
    buf: typing.List[T] = []
    try:
        while True:
            # Drain some of the iterable
            for _ in range(random.randint(1, bufsize - len(buf))):
                buf.append(next(iterator))

            # Shuffle and yield some of buffer
            random.shuffle(buf)
            for _ in range(random.randint(1, bufsize)):
                if buf:
                    yield buf.pop()
                else:
                    break
    except StopIteration:
        # Shuffle and yield rest of buffer
        random.shuffle(buf)
        while buf:
            yield buf.pop()
