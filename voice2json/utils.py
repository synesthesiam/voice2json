"""Utility methods for voice2json."""
import collections
import io
import logging
import os
import sys
import typing
import wave
from pathlib import Path

import jsonlines
import pydash

_LOGGER = logging.getLogger("voice2json.utils")

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
