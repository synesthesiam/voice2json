import io
import wave
import subprocess
import shlex
import logging
from pathlib import Path
from typing import Dict, Any, Union, List, TextIO, BinaryIO

import pydash

logger = logging.getLogger("utils")


def voice2json(
    *args, stream=False, text=True, input=None, profile_path=None, stderr=None
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
    """Converts WAV data to 16-bit, 16Khz mono."""
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
    """Converts WAV data to 16-bit, 16Khz mono WAV if necessary."""
    with io.BytesIO(wav_data) as wav_io:
        with wave.open(wav_io, "rb") as wav_file:
            rate, width, channels = (
                wav_file.getframerate(),
                wav_file.getsampwidth(),
                wav_file.getnchannels(),
            )
            if (rate != 16000) or (width != 2) or (channels != 1):
                # Do conversion
                if rate < 16000:
                    # Probably being given 8Khz audio
                    logger.warning(
                        f"Upsampling audio from {rate} Hz. Expect poor performance!"
                    )

                return convert_wav(profile, wav_data)
            else:
                # Return original data
                return wav_data


def buffer_to_wav(buffer: bytes) -> bytes:
    """Wraps a buffer of raw audio data (16-bit, 16Khz mono) in a WAV"""
    with io.BytesIO() as wav_buffer:
        with wave.open(wav_buffer, mode="wb") as wav_file:
            wav_file.setframerate(16000)
            wav_file.setsampwidth(2)
            wav_file.setnchannels(1)
            wav_file.writeframesraw(buffer)

        return wav_buffer.getvalue()


def wav_to_buffer(wav_bytes: bytes) -> bytes:
    """Extracts raw audio data from a WAV buffer."""
    with io.BytesIO(wav_bytes) as wav_buffer:
        with wave.open(wav_buffer) as wav_file:
            return wav_file.readframes(wav_file.getnframes())
