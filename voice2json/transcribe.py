"""Speech to text transcriptions methods."""
import argparse
import dataclasses
import itertools
import logging
import sys
from pathlib import Path

from .core import Voice2JsonCore
from .utils import print_json

_LOGGER = logging.getLogger("voice2json.transcribe")

# -----------------------------------------------------------------------------


async def transcribe(args: argparse.Namespace, core: Voice2JsonCore) -> None:
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
    except KeyboardInterrupt:
        pass
    finally:
        transcriber.stop()
