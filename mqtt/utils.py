import io
import sys
import wave
import subprocess
import shlex
import logging
from pathlib import Path
from typing import Dict, Any, Union, List, TextIO, BinaryIO

import pydash

logger = logging.getLogger("utils")


def voice2json(
    *args, stream=False, text=True, input=None, profile_path=None, stderr=sys.stderr
) -> Union[subprocess.Popen, TextIO, BinaryIO]:
    """Calls voice2json with the given arguments and current profile."""
    command = ["voice2json"]

    if profile_path is not None:
        # Add profile
        command.extend(["--profile", str(profile_path)])

    command.extend(list(args))
    logger.debug(command)

    if stream:
        if text:
            # Text-based stream
            return subprocess.Popen(
                command,
                universal_newlines=True,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=stderr,
            )
        else:
            # Binary stream
            return subprocess.Popen(
                command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr
            )
    else:
        if text:
            # Text-based I/O
            return io.StringIO(
                subprocess.check_output(
                    command, universal_newlines=True, input=input, stderr=stderr
                )
            )
        else:
            # Binary I/O
            return io.BytesIO(
                subprocess.check_output(command, input=input, stderr=stderr)
            )


def convert_wav(profile: Dict[str, Any], wav_data: bytes) -> bytes:
    """Converts WAV data to expected audio format."""
    convert_cmd_str = pydash.get(
        profile,
        "audio.convert-command",
        "sox -t wav - -r 16000 -e signed-integer -b 16 -c 1 -t wav -",
    )
    convert_cmd = shlex.split(convert_cmd_str)
    logger.debug(convert_cmd)
    return subprocess.run(
        convert_cmd, check=True, stdout=subprocess.PIPE, input=wav_data
    ).stdout


def maybe_convert_wav(profile: Dict[str, Any], wav_data: bytes) -> bytes:
    """Converts WAV data to expected audio format, if necessary."""
    expected_rate = int(pydash.get(profile, "audio.format.sample-rate-hertz", 16000))
    expected_width = int(pydash.get(profile, "audio.format.sample-width-bits", 16)) // 8
    expected_channels = int(pydash.get(profile, "audio.format.channel-count", 1))

    with io.BytesIO(wav_data) as wav_io:
        with wave.open(wav_io, "rb") as wav_file:
            rate, width, channels = (
                wav_file.getframerate(),
                wav_file.getsampwidth(),
                wav_file.getnchannels(),
            )
            if (
                (rate != expected_rate)
                or (width != expected_width)
                or (channels != expected_channels)
            ):
                logger.debug(
                    "Got %s Hz, %s byte(s), %s channel(s). Needed %s Hz, %s byte(s), %s channel(s)",
                    rate,
                    width,
                    channels,
                    expected_rate,
                    expected_width,
                    expected_channels,
                )

                # Do conversion
                if rate < expected_rate:
                    # Probably being given 8Khz audio
                    logger.warning(
                        "Upsampling audio from %s to %s Hz. Expect poor performance!",
                        rate,
                        expected_rate,
                    )

                return convert_wav(profile, wav_data)
            else:
                # Return original data
                return wav_data


def buffer_to_wav(profile: Dict[str, Any], buffer: bytes) -> bytes:
    """Wraps a buffer of raw audio data in a WAV"""
    rate = int(pydash.get(profile, "audio.format.sample-rate-hertz", 16000))
    width = int(pydash.get(profile, "audio.format.sample-width-bits", 16)) // 8
    channels = int(pydash.get(profile, "audio.format.channel-count", 1))

    with io.BytesIO() as wav_buffer:
        with wave.open(wav_buffer, mode="wb") as wav_file:
            wav_file.setframerate(rate)
            wav_file.setsampwidth(width)
            wav_file.setnchannels(channels)
            wav_file.writeframesraw(buffer)

        return wav_buffer.getvalue()


def wav_to_buffer(wav_bytes: bytes) -> bytes:
    """Extracts raw audio data from a WAV buffer."""
    with io.BytesIO(wav_bytes) as wav_buffer:
        with wave.open(wav_buffer) as wav_file:
            return wav_file.readframes(wav_file.getnframes())
