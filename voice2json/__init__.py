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


class Transcriber:
    """Base class of WAV transcribers."""

    def transcribe_wav(self, wav_data: bytes) -> Dict[str, Any]:
        pass

    def stop(self):
        pass


def get_transcriber(
    profile_dir: Path, profile: Dict[str, Any], open_transcription=False, debug=False
) -> Transcriber:
    # Load settings
    acoustic_model_type = pydash.get(
        profile, "speech-to-text.acoustic-model-type", "pocketsphinx"
    ).lower()

    if acoustic_model_type == "kaldi":
        # Kaldi
        return get_kaldi_transcriber(
            profile_dir, profile, open_transcription=open_transcription, debug=debug
        )
    elif acoustic_model_type == "julius":
        # Julius
        return get_julius_transcriber(
            profile_dir, profile, open_transcription=open_transcription, debug=debug
        )
    else:
        # Pocketsphinx (default)
        return get_pocketsphinx_transcriber(
            profile_dir, profile, open_transcription=open_transcription, debug=debug
        )


def get_pocketsphinx_transcriber(
    profile_dir: Path, profile: Dict[str, Any], open_transcription=False, debug=False
) -> Transcriber:
    from voice2json.speech.pocketsphinx import get_decoder, transcribe
    from voice2json.utils import maybe_convert_wav

    # Load settings
    acoustic_model = ppath(
        profile, profile_dir, "speech-to-text.acoustic-model", "acoustic_model"
    )

    if open_transcription:
        # Use base dictionary/language model
        dictionary = ppath(
            profile,
            profile_dir,
            "speech-to-text.base-dictionary",
            "base_dictionary.txt",
        )

        language_model = ppath(
            profile,
            profile_dir,
            "speech-to-text.base-language-model",
            "base_language_model.txt",
        )

    else:
        # Use custom dictionary/language model
        dictionary = ppath(
            profile, profile_dir, "speech-to-text.dictionary", "dictionary.txt"
        )

        language_model = ppath(
            profile, profile_dir, "speech-to-text.language-model", "language_model.txt"
        )

    mllr_matrix = ppath(
        profile, profile_dir, "speech-to-text.pocketsphinx.mllr-matrix", "mllr_matrix"
    )

    # Load deocder
    decoder = get_decoder(
        acoustic_model, dictionary, language_model, mllr_matrix, debug=debug
    )

    class PocketsphinxTranscriber(Transcriber):
        def __init__(self, decoder):
            self.decoder = decoder

        def transcribe_wav(self, wav_data: bytes) -> Dict[str, Any]:
            converted_wav_data = maybe_convert_wav(profile, wav_data)
            return transcribe(self.decoder, converted_wav_data)

    return PocketsphinxTranscriber(decoder)


def get_kaldi_transcriber(
    profile_dir: Path, profile: Dict[str, Any], open_transcription=False, debug=False
) -> Transcriber:
    from voice2json.utils import maybe_convert_wav

    # Load settings
    model_type = pydash.get(profile, "speech-to-text.kaldi.model-type", "")
    acoustic_model = ppath(
        profile, profile_dir, "speech-to-text.acoustic-model", "acoustic_model"
    )

    if open_transcription:
        # Use base graph
        graph_dir = ppath(
            profile, profile_dir, "speech-to-text.kaldi.base-graph-directory"
        ) or (acoustic_model / "model" / "graph")
    else:
        # Use custom graph
        graph_dir = ppath(
            profile, profile_dir, "speech-to-text.kaldi.graph-directory"
        ) or (acoustic_model / "graph")

    if model_type == "nnet3":
        logger.debug("Loading Kaldi nnet3 Python extension")

        # Use Python extension
        class KaldiExtensionTranscriber(Transcriber):
            def __init__(self, model_dir, graph_dir):
                self.model_dir = model_dir
                self.graph_dir = graph_dir
                self.model = None
                self.decoder = None

            def maybe_load_decoder(self):
                if self.decoder is None:
                    from kaldi_speech.nnet3 import KaldiNNet3OnlineModel, KaldiNNet3OnlineDecoder

                    logger.debug("Loading nnet3 model at %s (graph=%s)", self.model_dir, self.graph_dir)

                    self.model = KaldiNNet3OnlineModel(
                        str(self.model_dir), str(self.graph_dir)
                    )

                    logger.debug("Creating decoder")
                    self.decoder = KaldiNNet3OnlineDecoder(self.model)
                    logger.debug("Kaldi decoder loaded")

            def transcribe_wav(self, wav_data: bytes) -> Dict[str, Any]:
                self.maybe_load_decoder()

                # Convert WAV to 16-bit, 16Khz mono
                logger.debug("Decoding %s byte(s)", len(wav_data))
                start_time = time.time()
                converted_wav_data = maybe_convert_wav(profile, wav_data)

                with io.BytesIO(converted_wav_data) as wav_buffer:
                    with wave.open(wav_buffer, "rb") as wav_file:
                        sample_rate = wav_file.getframerate()
                        num_frames = wav_file.getnframes()
                        wav_duration = num_frames / float(sample_rate)

                        frames = wav_file.readframes(num_frames)
                        samples = struct.unpack_from("<%dh" % num_frames, frames)

                        # Decode
                        success = self.decoder.decode(
                            sample_rate, np.array(samples, dtype=np.float32), True
                        )
                        if success:
                            text, likelihood = self.decoder.get_decoded_string()
                        else:
                            text, likelihood = "", 0.0

                        decode_seconds = time.time() - start_time

                        return {
                            "text": text.strip(),
                            "transcribe_seconds": decode_seconds,
                            "wav_seconds": wav_duration,
                            "likelihood": likelihood,
                        }

        return KaldiExtensionTranscriber(acoustic_model, graph_dir)
    else:
        # Use kaldi-decode script
        class KaldiCommandLineTranscriber(Transcriber):
            def __init__(self, model_type, model_dir, graph_dir):
                self.model_type = model_type
                self.model_dir = model_dir
                self.graph_dir = graph_dir

            def transcribe_wav(self, wav_data: bytes) -> Dict[str, Any]:
                kaldi_cmd = [
                    "kaldi-decode",
                    "--model-type",
                    str(self.model_type),
                    "--model-dir",
                    str(self.model_dir),
                    "--graph-dir",
                    str(self.graph_dir),
                ]

                logger.debug(kaldi_cmd)

                with tempfile.NamedTemporaryFile(suffix=".wav", mode="wb") as temp_file:
                    # Convert WAV to 16-bit, 16Khz mono and save
                    converted_wav_data = maybe_convert_wav(profile, wav_data)
                    temp_file.write(converted_wav_data)

                    # Rewind
                    temp_file.seek(0)

                    kaldi_proc = subprocess.Popen(
                        kaldi_cmd,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        universal_newlines=True,
                    )

                    # Write path to WAV file
                    print(temp_file.name, file=kaldi_proc.stdin)
                    result_json, _ = kaldi_proc.communicate()

                    return json.loads(result_json)

        return KaldiCommandLineTranscriber(model_type, acoustic_model, graph_dir)


def get_julius_transcriber(
    profile_dir: Path, profile: Dict[str, Any], open_transcription=False, debug=False
) -> Transcriber:
    from voice2json.utils import maybe_convert_wav

    # Load settings
    acoustic_model = ppath(
        profile, profile_dir, "speech-to-text.acoustic-model", "acoustic_model"
    )

    if open_transcription:
        # Use base dictionary/language model
        dictionary = ppath(
            profile,
            profile_dir,
            "speech-to-text.base-dictionary",
            "base_dictionary.txt",
        )

        language_model = ppath(
            profile,
            profile_dir,
            "speech-to-text.base-language-model",
            "base_language_model.bin",
        )
    else:
        # Use custom dictionary/language model
        dictionary = ppath(
            profile, profile_dir, "speech-to-text.dictionary", "dictionary.txt"
        )

        language_model = ppath(
            profile, profile_dir, "speech-to-text.language-model", "language_model.txt"
        )

    class JuliusTranscriber(Transcriber):
        def __init__(self, model_dir, dictionary, language_model):
            self.model_dir = model_dir
            self.dictionary = dictionary
            self.language_model = language_model
            self.julius_proc = None
            self.temp_dir = None
            self.julius_out = None

        def _start_julius(self):
            logger.debug("Starting Julius")
            self.temp_dir = tempfile.TemporaryDirectory()

            fifo_path = os.path.join(self.temp_dir.name, "filelist")
            os.mkfifo(fifo_path)

            julius_cmd = [
                "julius",
                "-nosectioncheck",
                "-C",
                str(self.model_dir / "julius.jconf"),
                "-input",
                "file",
                "-filelist",
                fifo_path,
                "-nocutsilence",
                "-norealtime",
                "-v",
                str(self.dictionary),
            ]

            if not debug:
                julius_cmd.append("-quiet")

            dnn_conf = self.model_dir / "dnn.jconf"
            if dnn_conf.exists():
                # DNN model
                julius_cmd.extend(["-dnnconf", str(dnn_conf)])

            if language_model.suffix.lower() == ".txt":
                # ARPA forward n-grams
                julius_cmd.extend(["-nlr", str(language_model)])
            else:
                # Binary n-gram
                julius_cmd.extend(["-d", str(language_model)])

            logger.debug(julius_cmd)

            # Start Julius server
            self.julius_proc = subprocess.Popen(
                julius_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )

            self.julius_out = open(fifo_path, "w")

            # -----

            # Read until Julius has started
            line = self.julius_proc.stdout.readline().lower().strip()
            if "error" in line:
                raise Exception(line)

            while "system information end" not in line:
                line = self.julius_proc.stdout.readline().lower().strip()
                if "error" in line:
                    raise Exception(line)

            self.julius_in = self.julius_proc.stdout

            logger.debug("Julius started")

        def stop(self):
            if self.julius_out is not None:
                self.julius_out.close()
                self.julius_out = None

            if self.temp_dir is not None:
                self.temp_dir.cleanup()
                self.temp_dir = None

            if self.julius_proc is not None:
                logger.debug("Stopping Julius")
                self.julius_proc.terminate()
                self.julius_proc.wait()
                self.julius_proc = None
                logger.debug("Stopped Julius")

        def transcribe_wav(self, wav_data: bytes) -> Dict[str, Any]:
            if self.julius_proc is None:
                self._start_julius()

            # Compute WAV duration
            with io.BytesIO(wav_data) as wav_buffer:
                with wave.open(wav_buffer) as wav_file:
                    frames = wav_file.getnframes()
                    rate = wav_file.getframerate()
                    wav_duration = frames / float(rate)

            # Convert WAV to 16-bit, 16Khz mono
            converted_wav_data = maybe_convert_wav(profile, wav_data)

            # Write path to WAV file
            logger.debug("Sending %s byte(s) to Julius", len(converted_wav_data))
            start_time = time.time()

            with tempfile.NamedTemporaryFile(suffix=".wav", mode="wb+") as temp_file:
                temp_file.write(converted_wav_data)
                temp_file.seek(0)

                print(temp_file.name, file=self.julius_out)
                self.julius_out.flush()

                sentence_line = ""
                line = self.julius_in.readline().strip()
                logger.debug("Julius> %s", line)

                while True:
                    if line.startswith("sentence1:"):
                        sentence_line = line.split(":", maxsplit=1)[1]
                        break

                    if "error" in line.lower():
                        # Give up with an empty transcription
                        logger.warning(line)
                        break

                    line = self.julius_in.readline().strip()
                    logger.debug("Julius> %s", line)

                # Exclude <s> and </s>
                logger.debug(sentence_line)
                result_text = (
                    sentence_line.replace("<s>", "").replace("</s>", "").strip()
                )
                end_time = time.time()

            return {
                "text": result_text.strip(),
                "transcribe_seconds": end_time - start_time,
                "wav_seconds": wav_duration,
            }

    return JuliusTranscriber(acoustic_model, dictionary, language_model)


# -----------------------------------------------------------------------------


class Recognizer:
    """Base class of intent recognizers."""

    def recognize(self, text: str) -> Dict[str, Any]:
        pass


def get_recognizer(profile_dir: Path, profile: Dict[str, Any]) -> Recognizer:
    import pywrapfst as fst
    import networkx as nx
    from voice2json.intent.fsticuffs import (
        recognize,
        recognize_fuzzy,
        empty_intent,
        fst_to_graph,
    )

    # Load settings
    intent_fst_path = ppath(
        profile, profile_dir, "intent-recognition.intent-fst", "intent.fst"
    )
    stop_words_path = ppath(
        profile, profile_dir, "intent-recognition.stop-words", "stop_words.txt"
    )
    lower_case = pydash.get(profile, "intent-recognition.lower-case", False)
    fuzzy = pydash.get(profile, "intent-recognition.fuzzy", True)
    skip_unknown = pydash.get(profile, "intent-recognition.skip_unknown", True)

    # Load intent finite state transducer
    intent_fst = fst.Fst.read(str(intent_fst_path))

    # Load stop words (common words that can be safely ignored)
    stop_words: Set[str] = set()
    if (stop_words_path is not None) and stop_words_path.exists():
        stop_words.update(w.strip() for w in stop_words_path.read_text().splitlines())

    # Ignore words outside of input symbol table
    known_tokens: Set[str] = set()
    if skip_unknown:
        in_symbols = intent_fst.input_symbols()
        for i in range(in_symbols.num_symbols()):
            key = in_symbols.get_nth_key(i)
            token = in_symbols.find(i).decode()

            # Exclude meta tokens and <eps>
            if not (token.startswith("__") or token.startswith("<")):
                known_tokens.add(token)

    if fuzzy:
        # Convert to graph for fuzzy searching
        intent_graph = fst_to_graph(intent_fst)

        class FuzzyRecognizer(Recognizer):
            def __init__(self, intent_graph, known_tokens, lower_case, stop_words):
                self.intent_graph = intent_graph
                self.known_tokens = known_tokens
                self.lower_case = lower_case
                self.stop_words = stop_words

            def recognize(self, text: str) -> Dict[str, Any]:
                if self.lower_case:
                    text = text.lower()

                return recognize_fuzzy(
                    self.intent_graph,
                    text,
                    known_tokens=self.known_tokens,
                    stop_words=self.stop_words,
                )

        return FuzzyRecognizer(intent_graph, known_tokens, lower_case, stop_words)
    else:

        class StrictRecognizer(Recognizer):
            def __init__(self, intent_fst, known_tokens, lower_case):
                self.intent_fst = intent_fst
                self.known_tokens = known_tokens
                self.lower_case = lower_case

            def recognize(self, text: str) -> Dict[str, Any]:
                if self.lower_case:
                    text = text.lower()

                return recognize(self.intent_fst, text, self.known_tokens)

        return StrictRecognizer(intent_fst, known_tokens, lower_case)


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
