import io
import os
import sys
import json
import logging
import tempfile
import subprocess
import threading
import shutil
import wave
import time
import socket
import struct
import xml.etree.ElementTree as ET
from typing import Dict, Any
from pathlib import Path

logger = logging.getLogger("voice2json")

import pydash
import numpy as np

from voice2json.utils import ppath

# -----------------------------------------------------------------------------




# -----------------------------------------------------------------------------


class Tuner:
    def tune(self, examples_dir: Path) -> None:
        pass


def get_tuner(profile_dir: Path, profile: Dict[str, Any]) -> Tuner:
    from voice2json.utils import should_convert_wav, convert_wav

    # Load settings
    acoustic_model_type = pydash.get(
        profile, "speech-to-text.acoustic-model-type", "pocketsphinx"
    ).lower()

    if acoustic_model_type != "pocketsphinx":
        logger.fatal("Acoustic model tuning is only availble for pocketsphinx for now.")
        sys.exit(1)

    acoustic_model = ppath(
        profile, profile_dir, "speech-to-text.acoustic-model", "acoustic_model"
    )
    dictionary = ppath(
        profile, profile_dir, "speech-to-text.dictionary", "dictionary.txt"
    )
    mllr_matrix = ppath(
        profile, profile_dir, "speech-to-text.mllr-matrix", "mllr_matrix"
    )

    class SphinxTuner(Tuner):
        def __init__(self, acoustic_model, dictionary, mllr_matrix):
            self.acoustic_model = acoustic_model
            self.dictionary = dictionary
            self.mllr_matrix = mllr_matrix

        def tune(self, examples_dir):
            programs = ["bw", "pocketsphinx_mdef_convert", "sphinx_fe", "mllr_solve"]
            for program in programs:
                if not shutil.which(program):
                    logger.fatal(f"Missing {program}. Did you install sphinxtrain?")
                    return

            with tempfile.TemporaryDirectory() as temp_dir_str:
                # temp_dir = Path(temp_dir_str)
                temp_dir = Path("/tmp/tune")
                temp_dir_str = str(temp_dir)

                # Create mdef.txt
                mdef_path = temp_dir / "mdef.txt"
                mdef_command = [
                    "pocketsphinx_mdef_convert",
                    "-text",
                    str(self.acoustic_model / "mdef"),
                    str(mdef_path),
                ]

                logger.debug(mdef_command)
                subprocess.check_call(mdef_command)

                # Write fileids and transcriptions.txt
                fileids_path = temp_dir / "fileids"
                transcription_path = temp_dir / "transcriptions.txt"

                with open(fileids_path, "w") as fileids_file:
                    with open(transcription_path, "w") as transcription_file:
                        for wav_path in examples_dir.glob("*.wav"):
                            temp_wav_path = temp_dir / wav_path.name

                            with open(wav_path, "rb") as wav_file:
                                if should_convert_wav(profile, wav_file):
                                    logger.debug("Converting %s", wav_path)

                                    # Convert/copy WAV file
                                    wav_file.seek(0)
                                    converted_wav_data = convert_wav(
                                        profile, wav_file.read()
                                    )
                                    temp_wav_path.write_bytes(converted_wav_data)
                                else:
                                    # Create symbolic link to actual WAV file
                                    temp_wav_path.symlink_to(wav_path)

                            text_path = examples_dir / f"{wav_path.stem}.txt"
                            intent_path = examples_dir / f"{wav_path.stem}.json"

                            if text_path.exists():
                                text = text_path.read_text().strip()
                            elif intent_path.exists():
                                with open(intent_path, "r") as intent_file:
                                    text = json.load(intent_file)["text"]
                            else:
                                logger.warn(
                                    f"Skipping {wav_path} (no transcription or intent files)"
                                )
                                continue

                            # File id does not have extension
                            file_id = wav_path.stem
                            print(file_id, file=fileids_file)

                            print(
                                "%s (%s.wav)" % (text, file_id), file=transcription_file
                            )

                # Extract features
                feat_params_path = self.acoustic_model / "feat.params"
                feature_cmd = [
                    "sphinx_fe",
                    "-argfile",
                    str(feat_params_path),
                    "-samprate",
                    "16000",
                    "-c",
                    str(fileids_path),
                    "-di",
                    temp_dir_str,
                    "-do",
                    temp_dir_str,
                    "-ei",
                    "wav",
                    "-eo",
                    "mfc",
                    "-mswav",
                    "yes",
                ]

                logger.debug(feature_cmd)
                subprocess.check_call(feature_cmd)

                # Generate statistics
                bw_args = [
                    "-hmmdir",
                    str(self.acoustic_model),
                    "-dictfn",
                    str(self.dictionary),
                    "-ctlfn",
                    str(fileids_path),
                    "-lsnfn",
                    str(transcription_path),
                    "-cepdir",
                    temp_dir_str,
                    "-moddeffn",
                    str(mdef_path),
                    "-accumdir",
                    temp_dir_str,
                    "-ts2cbfn",
                    ".cont.",
                ]  # assume continuous model

                feature_transform_path = self.acoustic_model / "feature_transform"
                if feature_transform_path.exists():
                    # Required if feature transform exists!
                    bw_args.extend(["-lda", str(feature_transform_path)])

                # Add model parameters
                with open(feat_params_path, "r") as feat_params_file:
                    for line in feat_params_file:
                        line = line.strip()
                        if len(line) > 0:
                            param_parts = line.split(maxsplit=1)
                            param_name = param_parts[0]
                            # Only add compatible bw args
                            if param_name in SPHINX_BW_ARGS:
                                # e.g., -agc none
                                bw_args.extend([param_name, param_parts[1]])

                bw_command = ["bw", "-timing", "no"] + bw_args
                logger.debug(bw_command)
                subprocess.check_call(bw_command)

                solve_command = [
                    "mllr_solve",
                    "-meanfn",
                    str(self.acoustic_model / "means"),
                    "-varfn",
                    str(self.acoustic_model / "variances"),
                    "-outmllrfn",
                    str(self.mllr_matrix),
                    "-accumdir",
                    temp_dir_str,
                ]

                logger.debug(solve_command)
                subprocess.check_call(solve_command)

                logger.debug("Tuning succeeded")

    # -----------------------------------------------------------------------------

    return SphinxTuner(acoustic_model, dictionary, mllr_matrix)


# Pulled from a run of sphinxtrain/bw
SPHINX_BW_ARGS = set(
    [
        "-2passvar",
        "-abeam",
        "-accumdir",
        "-agc",
        "-agcthresh",
        "-bbeam",
        "-cb2mllrfn",
        "-cepdir",
        "-cepext",
        "-ceplen",
        "-ckptintv",
        "-cmn",
        "-cmninit",
        "-ctlfn",
        "-diagfull",
        "-dictfn",
        "-example",
        "-fdictfn",
        "-feat",
        "-fullsuffixmatch",
        "-fullvar",
        "-hmmdir",
        "-latdir",
        "-latext",
        "-lda",
        "-ldadim",
        "-lsnfn",
        "-lw",
        "-maxuttlen",
        "-meanfn",
        "-meanreest",
        "-mixwfn",
        "-mixwreest",
        "-mllrmat",
        "-mmie",
        "-mmie_type",
        "-moddeffn",
        "-mwfloor",
        "-npart",
        "-nskip",
        "-outphsegdir",
        "-outputfullpath",
        "-part",
        "-pdumpdir",
        "-phsegdir",
        "-phsegext",
        "-runlen",
        "-sentdir",
        "-sentext",
        "-spthresh",
        "-svspec",
        "-timing",
        "-tmatfn",
        "-tmatreest",
        "-topn",
        "-tpfloor",
        "-ts2cbfn",
        "-varfloor",
        "-varfn",
        "-varnorm",
        "-varreest",
        "-viterbi",
    ]
)
