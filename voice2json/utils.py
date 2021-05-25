"""Utility methods for voice2json."""
import asyncio
import collections
import io
import logging
import os
import platform
import random
import ssl
import sys
import typing
import wave
from collections import deque
from pathlib import Path

import aiofiles
import aiohttp
import pydash

_LOGGER = logging.getLogger("voice2json.utils")
T = typing.TypeVar("T")
DEFAULT_URL_FORMAT = (
    "https://raw.githubusercontent.com/synesthesiam/{profile}/master/{file}"
)

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
        if isinstance(v, collections.abc.Mapping) and (k in base_dict):
            recursive_update(base_dict[k], v)
        else:
            base_dict[k] = v


# -----------------------------------------------------------------------------


def print_json(value: typing.Any, out_file=sys.stdout) -> None:
    """Print a single line of JSON to stdout."""
    import jsonlines

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


# -----------------------------------------------------------------------------

# url, path, file_key, done, bytes_downloaded, bytes_expected
DownloadStatusType = typing.Callable[
    [str, Path, str, bool, int, typing.Optional[int]], None
]


async def download_file(
    url: str,
    path: Path,
    file_key: str = "",
    bytes_expected: typing.Optional[int] = None,
    session: typing.Optional[aiohttp.ClientSession] = None,
    ssl_context: typing.Optional[ssl.SSLContext] = None,
    chunk_size: int = 4096,
    status_fun: typing.Optional[DownloadStatusType] = None,
) -> typing.Tuple[str, int, typing.Optional[int]]:
    """
    Downloads a single file to a destination path.
    Optionally reports status by calling status_fun.

    Returns url, bytes downloaded, and bytes expected.
    """
    close_session = session is None
    session = session or aiohttp.ClientSession()
    assert session

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        _LOGGER.debug("Downloading %s to %s", url, str(path))

        bytes_downloaded: int = 0

        if url.startswith("file://"):
            # Use file system
            file_path = Path(url[7:])
            async with aiofiles.open(file_path, "r") as local_file:
                with open(path, "wb") as out_file:
                    while True:
                        chunk = await local_file.read(chunk_size)
                        if not chunk:
                            break

                        out_file.write(chunk)
                        bytes_downloaded += len(chunk)

                        # Report status
                        if status_fun:
                            status_fun(
                                url,
                                path,
                                file_key,
                                False,
                                bytes_downloaded,
                                bytes_expected,
                            )
        else:
            # Actually download
            async with session.get(
                url, ssl=ssl_context, raise_for_status=True
            ) as response:
                with open(path, "wb") as out_file:
                    async for chunk in response.content.iter_chunked(chunk_size):
                        out_file.write(chunk)
                        bytes_downloaded += len(chunk)

                        # Report status
                        if status_fun:
                            status_fun(
                                url,
                                path,
                                file_key,
                                False,
                                bytes_downloaded,
                                bytes_expected,
                            )

        # Final status
        if status_fun:
            status_fun(url, path, file_key, True, bytes_downloaded, bytes_expected)
    finally:
        if close_session:
            await session.close()

    return url, bytes_downloaded, bytes_expected


def get_profile_downloads(
    profile_name: str,
    files_dict: typing.Dict[str, typing.Any],
    profile_dir: typing.Union[str, Path],
    grapheme_to_phoneme: bool = False,
    open_transcription: bool = False,
    mixed_language_model: bool = False,
    text_to_speech: bool = False,
    with_examples: bool = True,
    only_missing: bool = True,
    machine: typing.Optional[str] = None,
) -> typing.Iterable[typing.Dict[str, typing.Any]]:
    """Yields a dict for each missing profile file with 'url' and 'file' keys"""
    profile_dir = Path(profile_dir)
    if not machine:
        machine = platform.machine()

    # Format string for file URL.
    # {profile} = profile name (e.g., en-us_kaldi-zamia)
    # {file} = relative file path (e.g. acoustic_model/conf/mfcc.conf)
    # {machine} = platform machine (e.g., x86_64)
    url_format = files_dict.get("url_format", DEFAULT_URL_FORMAT)

    # Add files to downloads
    for condition, files in files_dict.items():
        if not isinstance(files, collections.abc.Mapping):
            continue

        # Filter based on condition and arguments
        if (
            (not grapheme_to_phoneme and condition == "grapheme-to-phoneme")
            or (not open_transcription and condition == "open-transcription")
            or (not mixed_language_model and condition == "mixed-language-model")
            or (not text_to_speech and condition == "text-to-speech")
            or (not with_examples and condition == "examples")
        ):
            _LOGGER.debug("Excluding condition %s", condition)
            continue

        for file_path, file_info in files.items():
            _LOGGER.debug("Checking %s", file_path)

            if only_missing:
                # Check if file is missing
                real_file_name = file_info.get("file-name")
                if real_file_name:
                    # Use combined/unzipped file name
                    expected_path = (
                        profile_dir / Path(file_path).parent / real_file_name
                    )
                else:
                    expected_path = profile_dir / file_path

                if expected_path.is_file():
                    # Skip existing file
                    _LOGGER.debug("Excluding %s (%s exists)", file_path, expected_path)
                    continue

                _LOGGER.debug("%s does not exist (%s)", expected_path, file_path)

            # Check machine
            platforms = file_info.get("platform")
            if platforms:
                machine_match = False
                for platform_matches in platforms:
                    if machine == platform_matches.get("machine", ""):
                        machine_match = True
                        break

                if not machine_match:
                    _LOGGER.debug("Excluding %s (machine mismatch)", file_path)
                    continue

            # Add extra info to file info
            download_info = dict(file_info)
            download_info["file"] = file_path
            download_info["profile"] = profile_name
            download_info["url"] = url_format.format(
                profile=profile_name, file=file_path
            )
            download_info["profile-directory"] = str(profile_dir)

            yield download_info


# -----------------------------------------------------------------------------


async def reassemble_large_files(large_paths: typing.Sequence[typing.Union[str, Path]]):
    """Unzips and combines files that have been split"""
    first_log = True

    for target_path in large_paths:
        gzip_path = Path(str(target_path) + ".gz")
        part_paths = sorted(list(gzip_path.parent.glob(f"{gzip_path.name}.part-*")))
        if part_paths:
            if first_log:
                _LOGGER.info("Reassembling large files...")
                first_log = False

            _LOGGER.debug(
                "Reassembling %s from %s part(s) into %s",
                gzip_path,
                len(part_paths),
                target_path,
            )

            # Concatenate paths to together
            cat_command = ["cat"] + [str(p) for p in part_paths]
            _LOGGER.debug(cat_command)

            with open(gzip_path, "wb") as gzip_file:
                await async_run(cat_command, stdout=gzip_file)

        if gzip_path.is_file():
            # Unzip single file
            if first_log:
                _LOGGER.info("Reassembling large files...")
                first_log = False

            unzip_command = ["gunzip", "-f", "--stdout", str(gzip_path)]
            _LOGGER.debug(unzip_command)

            with open(target_path, "wb") as target_file:
                await async_run(unzip_command, stdout=target_file)

            # Delete zip file
            gzip_path.unlink()

        # Delete unneeded .gz-part files
        for part_path in part_paths:
            part_path.unlink()


# -----------------------------------------------------------------------------


async def async_run(command: typing.List[str], **kwargs):
    """Run a command asynchronously."""
    process = await asyncio.create_subprocess_exec(*command, **kwargs)
    await process.wait()
    assert process.returncode == 0, "Command failed"
