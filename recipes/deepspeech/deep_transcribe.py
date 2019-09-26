#!/usr/bin/env python3
import sys
import argparse
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger("deep_transcribe")

import numpy as np
from deepspeech import Model


def main():
    parser = argparse.ArgumentParser(
        prog="deep_transcribe.py",
        description="Transcribe WAV files using Mozilla's DeepSpeech",
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

    # Read raw audio data.
    # Assume 16-bit 16Khz mono.
    audio_data = sys.stdin.buffer.read()

    # DeepSpeech expects an int16 numpy array
    logging.debug(f"Transcribing {len(audio_data)} byte(s)")
    text = ds.stt(np.frombuffer(audio_data, dtype=np.int16), 16000)
    print(text)


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
