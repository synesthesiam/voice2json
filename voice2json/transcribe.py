"""Speech to text transcriptions methods."""
import argparse
import dataclasses
import itertools
import logging
import sys
import threading
import time
import typing
from pathlib import Path
from queue import Queue

import pydash

from .core import Voice2JsonCore
from .utils import print_json

_LOGGER = logging.getLogger("voice2json.transcribe")

# -----------------------------------------------------------------------------


async def transcribe_wav(args: argparse.Namespace, core: Voice2JsonCore) -> None:
    """Speech to text from WAV file(s)."""
    from rhasspyasr import Transcription

    # Make sure profile has been trained
    assert core.check_trained(), "Not trained"

    # Get speech to text transcriber for profile
    transcriber = core.get_transcriber(open_transcription=args.open, debug=args.debug)

    # Directory to report WAV file names relative to
    relative_dir = (
        None if args.relative_directory is None else Path(args.relative_directory)
    )

    try:
        if args.wav_file or args.stdin_files:
            # Read WAV file paths
            wav_files = args.wav_file
            if args.stdin_files:
                _LOGGER.debug("Reading file paths from stdin")
                wav_files = itertools.chain(wav_files, sys.stdin)

            for wav_path_str in wav_files:
                wav_path_str = wav_path_str.strip()

                # Load and convert
                wav_path = Path(wav_path_str)
                _LOGGER.debug("Transcribing %s", wav_path)

                wav_data = await core.maybe_convert_wav(wav_path.read_bytes())

                # Transcribe
                transcription = (
                    transcriber.transcribe_wav(wav_data) or Transcription.empty()
                )
                result = dataclasses.asdict(transcription)

                if relative_dir is None:
                    # Add name of WAV file to result
                    result["wav_name"] = wav_path.name
                else:
                    # Make relative to some directory
                    result["wav_name"] = str(wav_path.relative_to(relative_dir))

                print_json(result)
        else:
            # Read WAV data from stdin
            _LOGGER.debug("Reading WAV data from stdin")

            if args.input_size:
                # Number of bytes is on separate line
                line = sys.stdin.buffer.readline().strip()
                if not line:
                    return

                num_bytes = int(line)
                while num_bytes > 0:
                    # Read in WAV
                    wav_data = sys.stdin.buffer.read(num_bytes)
                    while len(wav_data) < num_bytes:
                        wav_data = sys.stdin.buffer.read(num_bytes - len(wav_data))

                    # Transcribe
                    wav_data = await core.maybe_convert_wav(wav_data)
                    transcription = (
                        transcriber.transcribe_wav(wav_data) or Transcription.empty()
                    )
                    result = dataclasses.asdict(transcription)

                    print_json(result)

                    # Next WAV
                    line = sys.stdin.buffer.readline().strip()
                    if not line:
                        break

                    num_bytes = int(line)
            else:
                # Load and convert entire input
                wav_data = await core.maybe_convert_wav(sys.stdin.buffer.read())

                # Transcribe
                transcription = (
                    transcriber.transcribe_wav(wav_data) or Transcription.empty()
                )
                result = dataclasses.asdict(transcription)

                print_json(result)
    finally:
        transcriber.stop()


# -----------------------------------------------------------------------------


async def transcribe_stream(args: argparse.Namespace, core: Voice2JsonCore) -> None:
    """Speech to text from WAV file(s)."""
    from rhasspyasr import Transcription
    from rhasspysilence import VoiceCommand, VoiceCommandResult

    # Make sure profile has been trained
    assert core.check_trained(), "Not trained"

    wav_sink = None
    wav_dir = None
    if args.wav_sink:
        wav_sink_path = Path(args.wav_sink)
        if wav_sink_path.is_dir():
            # Directory to write WAV files
            wav_dir = wav_sink_path
        else:
            # Single WAV file to write
            wav_sink = open(args.wav_sink, "wb")

    event_sink = None
    if args.event_sink:
        if args.event_sink == "-":
            event_sink = sys.stdout
        else:
            event_sink = open(args.event_sink, "w")

    # Record command
    recorder = core.get_command_recorder()
    recorder.start()

    voice_command: typing.Optional[VoiceCommand] = None

    # Expecting raw 16-bit, 16Khz mono audio
    audio_source = await core.make_audio_source(args.audio_source)

    # Audio settings
    sample_rate = int(pydash.get(core.profile, "audio.format.sample-rate-hertz", 16000))
    sample_width = (
        int(pydash.get(core.profile, "audio.format.sample-width-bits", 16)) // 8
    )
    channels = int(pydash.get(core.profile, "audio.format.channel-count", 1))

    # Get speech to text transcriber for profile
    transcriber = core.get_transcriber(open_transcription=args.open, debug=args.debug)

    # Run transcription in separate thread
    frame_queue: "Queue[typing.Optional[bytes]]" = Queue()

    def audio_stream() -> typing.Iterable[bytes]:
        """Read audio chunks from queue and yield."""
        frames = frame_queue.get()
        while frames:
            yield frames
            frames = frame_queue.get()

    def transcribe_proc():
        """Transcribe live audio stream indefinitely."""
        while True:
            # Get result of transcription
            transcribe_result = transcriber.transcribe_stream(
                audio_stream(), sample_rate, sample_width, channels
            )

            _LOGGER.debug("Transcription result: %s", transcribe_result)

            transcribe_result = transcribe_result or Transcription.empty()
            transcribe_dict = dataclasses.asdict(transcribe_result)
            transcribe_dict["timeout"] = is_timeout

            print_json(transcribe_dict)

    threading.Thread(target=transcribe_proc, daemon=True).start()

    # True if current voice command timed out
    is_timeout = False

    # Number of events for pending voice command
    event_count = 0

    # Number of transcriptions that have happened
    num_transcriptions = 0

    try:
        chunk = await audio_source.read(args.chunk_size)
        while chunk:
            # Look for speech/silence
            voice_command = recorder.process_chunk(chunk)

            if event_sink:
                # Print outstanding events
                for event in recorder.events[event_count:]:
                    print_json(dataclasses.asdict(event), out_file=event_sink)

                event_count = len(recorder.events)

            if voice_command:
                is_timeout = voice_command.result == VoiceCommandResult.FAILURE

                # Force transcription
                frame_queue.put(None)

                # Reset
                audio_data = recorder.stop()
                if wav_dir:
                    # Write WAV to directory
                    wav_path = (wav_dir / time.strftime(args.wav_filename)).with_suffix(
                        ".wav"
                    )
                    wav_bytes = core.buffer_to_wav(audio_data)
                    wav_path.write_bytes(wav_bytes)
                    _LOGGER.debug("Wrote %s (%s byte(s))", wav_path, len(wav_bytes))
                elif wav_sink:
                    # Write to WAV file
                    wav_bytes = core.buffer_to_wav(audio_data)
                    wav_sink.write(wav_bytes)
                    _LOGGER.debug(
                        "Wrote %s (%s byte(s))", args.wav_sink, len(wav_bytes)
                    )

                num_transcriptions += 1

                # Check exit count
                if (args.exit_count is not None) and (
                    num_transcriptions >= args.exit_count
                ):
                    _LOGGER.debug("Exit count reached")
                    break

                recorder.start()
            else:
                # Add to current command
                frame_queue.put(chunk)

            # Next audio chunk
            chunk = await audio_source.read(args.chunk_size)
    finally:
        transcriber.stop()

        try:
            await audio_source.close()
        except Exception:
            pass
