#!/usr/bin/env python3
import logging

logger = logging.getLogger("pocketsphinx")

import os
import sys
import jsonlines
import time
import argparse
import threading
import json
from typing import Optional, Dict, Any
from pathlib import Path

import pocketsphinx

# -------------------------------------------------------------------------------------------------


def get_decoder(
    acoustic_model: Path,
    dictionary: Path,
    language_model: Path,
    mllr_matrix: Optional[Path] = None,
    debug: bool = False,
) -> pocketsphinx.Decoder:
    """Loads the pocketsphinx decoder from command-line arguments."""
    start_time = time.time()
    decoder_config = pocketsphinx.Decoder.default_config()
    decoder_config.set_string("-hmm", str(acoustic_model))
    decoder_config.set_string("-dict", str(dictionary))
    decoder_config.set_string("-lm", str(language_model))

    if not debug:
        decoder_config.set_string("-logfn", os.devnull)

    if mllr_matrix is not None:
        decoder_config.set_string("-mllr", str(mllr_matrix))

    decoder = pocketsphinx.Decoder(decoder_config)
    end_time = time.time()

    logger.debug(f"Successfully loaded decoder in {end_time - start_time} second(s)")

    return decoder


# -------------------------------------------------------------------------------------------------


def transcribe(
    decoder: pocketsphinx.Decoder, audio_data: bytes, nbest: int = 0
) -> Dict[str, Any]:
    """Transcribes audio data to text."""
    # Process data as an entire utterance
    start_time = time.time()
    decoder.start_utt()
    decoder.process_raw(audio_data, False, True)
    decoder.end_utt()
    end_time = time.time()

    logger.debug(f"Decoded audio in {end_time - start_time} second(s)")

    transcription = ""
    decode_seconds = end_time - start_time
    likelihood = 0.0
    score = 0

    hyp = decoder.hyp()
    if hyp is not None:
        likelihood = decoder.get_logmath().exp(hyp.prob)
        transcription = hyp.hypstr

    result = {
        "text": transcription,
        "transcribe_seconds": decode_seconds,
        "likelihood": likelihood,
    }

    if nbest > 0:
        # Include alternative transcriptions
        result["nbest"] = {nb.hypstr: nb.score for nb in decoder.nbest()[:nbest]}

    return result
