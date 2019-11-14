#!/usr/bin/env python3
import io
import sys
import json
import wave
import time
import argparse
import logging
import subprocess
import shlex
from pathlib import Path
from typing import Dict, Any, Tuple

logger = logging.getLogger("deep_transcribe")

import jsonlines
import numpy as np
from deepspeech import Model


def main():
    parser = argparse.ArgumentParser(
        prog="deep_transcribe.py",
        description="Transcribe WAV files using Mozilla's DeepSpeech",
    )
    parser.add_argument(
        "wav_file", nargs="*", default=[], help="WAV files to transcribe"
    )
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG log to console"
    )
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)

    model_dir = Path("model")

    # Paths to parts of model
    model_path = model_dir / "output_graph.pb"
    alphabet_path = model_dir / "alphabet.txt"
    lm_path = model_dir / "lm.binary"
    trie_path = model_dir / "trie"

    # Beam width used in the CTC decoder when building candidate transcriptions
    beam_width = 500  # default 500

    # The alpha hyperparameter of the CTC decoder. Language Model weight
    lm_weight = 1.50  # default 1.50

    # Valid word insertion weight. This is used to lessen the word insertion penalty
    # when the inserted word is part of the vocabulary
    valid_word_count_weight = 2.10  # default is 2.10

    # Number of MFCC features to use
    n_features = 26

    # Size of the context window used for producing timesteps in the input vector
    n_context = 9

    # Load model
    logging.debug(f"Loading model from {model_dir}")
    ds = Model(str(model_path), n_features, n_context, str(alphabet_path), beam_width)

    # Load decoder
    ds.enableDecoderWithLM(
        str(alphabet_path),
        str(lm_path),
        str(trie_path),
        lm_weight,
        valid_word_count_weight,
    )

    def transcribe_raw(audio_data: bytes) -> Dict[str, Any]:
        start_time = time.time()
        text = ds.stt(np.frombuffer(audio_data, dtype=np.int16), 16000)
        return {"text": text, "transcribe_seconds": time.time() - start_time}

    def print_json(value):
        with jsonlines.Writer(sys.stdout) as out:
            out.write(value)

    if len(args.wav_file) > 0:
        # Process WAV files from arguments
        for wav_path_str in args.wav_file:
            wav_path = Path(wav_path_str)
            logger.debug("Transcribing %s", wav_path)
            wav_data = wav_path.read_bytes()
            audio_data, wav_seconds = maybe_convert_wav(wav_data)

            # Output jsonl
            result = transcribe_raw(audio_data)
            result["wav_name"] = wav_path.name
            result["wav_seconds"] = wav_seconds
            print_json(result)

    else:
        # Assume WAV data on stdin
        logger.debug("Reading WAV data from stdin")
        wav_data = sys.stdin.buffer.read()
        audio_data, wav_seconds = maybe_convert_wav(wav_data)

        # Output jsonl
        result = transcribe_raw(audio_data)
        result["wav_seconds"] = wav_seconds
        print_json(result)


# -----------------------------------------------------------------------------


def convert_wav(wav_data: bytes) -> bytes:
    """Converts WAV data to 16-bit, 16Khz mono raw."""
    convert_cmd_str = "sox -t wav - -r 16000 -e signed-integer -b 16 -c 1 -t raw -"
    convert_cmd = shlex.split(convert_cmd_str)
    logger.debug(convert_cmd)
    return subprocess.run(
        convert_cmd, check=True, stdout=subprocess.PIPE, input=wav_data
    ).stdout


def maybe_convert_wav(wav_data: bytes) -> Tuple[bytes, float]:
    """Converts WAV data to 16-bit, 16Khz mono WAV if necessary."""
    with io.BytesIO(wav_data) as wav_io:
        with wave.open(wav_io, "rb") as wav_file:
            frames = wav_file.getnframes()
            rate = wav_file.getframerate()
            wav_duration = frames / float(rate)
            width, channels = (wav_file.getsampwidth(), wav_file.getnchannels())
            if (rate != 16000) or (width != 2) or (channels != 1):
                # Do conversion
                return convert_wav(wav_data), wav_duration
            else:
                # Return original data
                return wav_file.readframes(frames), wav_duration


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
