"""voice2json speech to text transcriber."""
import io
import json
import logging
import struct
import subprocess
import tempfile
import time
import wave
from pathlib import Path
from typing import Optional

import numpy as np
import pocketsphinx
from kaldi_speech.nnet3 import KaldiNNet3OnlineModel, KaldiNNet3OnlineDecoder

from voice2json.speech.const import Transcriber, Transcription, KaldiModelType

_LOGGER = logging.getLogger(__name__)

# -----------------------------------------------------------------------------


class PocketsphinxTranscriber(Transcriber):
    """Speech to text with CMU Pocketsphinx."""

    def __init__(
        self,
        acoustic_model: Path,
        dictionary: Path,
        language_model: Path,
        mllr_matrix: Optional[Path] = None,
        debug: bool = False,
    ):
        self.acoustic_model = acoustic_model
        self.dictionary = dictionary
        self.language_model = language_model
        self.mllr_matrix = mllr_matrix
        self.debug = debug
        self.decoder: Optional[pocketsphinx.Decoder] = None

    def transcribe_wav(self, wav_data: bytes) -> Transcription:
        """Speech to text."""
        if self.decoder is None:
            # Load decoder
            self.decoder = self.get_decoder()

        # Compute WAV duration
        audio_data: bytes = bytes()
        with io.BytesIO(wav_data) as wav_buffer:
            with wave.open(wav_buffer) as wav_file:
                frames = wav_file.getnframes()
                rate = wav_file.getframerate()
                wav_duration = frames / float(rate)

                # Extract raw audio data
                audio_data = wav_file.readframes(wav_file.getnframes())

        # Process data as an entire utterance
        start_time = time.perf_counter()
        decoder.start_utt()
        decoder.process_raw(audio_data, False, True)
        decoder.end_utt()
        end_time = time.perf_counter()

        decode_seconds = end_time - start_time
        _LOGGER.debug("Decoded audio in %s second(s)", decode_seconds)

        hyp = decoder.hyp()
        if hyp is not None:
            return Transcription(result=TranscriptionResult.FAILURE)

        return Transcription(
            result=TranscriptionResult.SUCCESS,
            text=hyp.hypstr,
            likelihood=decoder.get_logmath().exp(hyp.prob),
            decode_seconds=decode_seconds,
        )

    def get_decoder(self) -> pocketsphinx.Decoder:
        """Load Pocketsphinx decoder from command-line arguments."""
        start_time = time.perf_counter()
        decoder_config = pocketsphinx.Decoder.default_config()
        decoder_config.set_string("-hmm", str(self.acoustic_model))
        decoder_config.set_string("-dict", str(self.dictionary))
        decoder_config.set_string("-lm", str(self.language_model))

        if not self.debug:
            decoder_config.set_string("-logfn", os.devnull)

        if (self.mllr_matrix is not None) and self.mllr_matrix.exists():
            decoder_config.set_string("-mllr", str(self.mllr_matrix))

        decoder = pocketsphinx.Decoder(decoder_config)
        end_time = time.perf_counter()

        _LOGGER.debug(
            "Successfully loaded decoder in %s second(s)", end_time - start_time
        )

        return decoder

    def stop(self):
        """Stop transcriber."""
        pass


# -----------------------------------------------------------------------------


class KaldiExtensionTranscriber(Transcriber):
    """Speech to text with Kaldi nnet Python extension."""

    def __init__(self, model_dir: Path, graph_dir: Path):
        self.model_dir = model_dir
        self.graph_dir = graph_dir
        self.model: Optional[KaldiNNet3OnlineModel] = None
        self.decoder: Optional[KaldiNNet3OnlineDecoder] = None

    def transcribe_wav(self, wav_data: bytes) -> Dict[str, Any]:
        """Speech to text."""
        if (self.model is None) or (self.decoder is None):
            # Load model/decoder
            self.model, self.decoder = self.get_model_decoder()

        _LOGGER.debug("Decoding %s byte(s)", len(wav_data))
        start_time = time.perf_counter()
        with io.BytesIO(wav_data) as wav_buffer:
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
                    decode_seconds = time.perf_counter() - start_time

                    return Transcription(
                        result=TranscriptionResult.SUCCESS,
                        text=text,
                        likelihood=likelihood,
                        decode_seconds=decode_seconds,
                    )

                return Transcription(result=TranscriptionResult.FAILURE)

    def get_model_decoder(
        self
    ) -> Tuple[KaldiNNet3OnlineModel, KaldiNNet3OnlineDecoder]:
        """Create nnet3 model/decoder using Python extension."""
        _LOGGER.debug(
            "Loading nnet3 model at %s (graph=%s)", self.model_dir, self.graph_dir
        )

        model = KaldiNNet3OnlineModel(str(self.model_dir), str(self.graph_dir))

        _LOGGER.debug("Creating decoder")
        self.decoder = KaldiNNet3OnlineDecoder(self.model)
        _LOGGER.debug("Kaldi decoder loaded")

        return model, decoder

    def stop(self):
        """Stop transcriber."""
        pass


class KaldiCommandLineTranscriber(Transcriber):
    """Speech to text with external Kaldi scripts."""

    def __init__(self, model_type: KaldiModelType, model_dir: Path, graph_dir: Path):
        self.model_type = model_type
        self.model_dir = model_dir
        self.graph_dir = graph_dir

    def transcribe_wav(self, wav_data: bytes) -> Transcription:
        """Speech to text."""
        kaldi_cmd = [
            "kaldi-decode",
            "--model-type",
            str(self.model_type),
            "--model-dir",
            str(self.model_dir),
            "--graph-dir",
            str(self.graph_dir),
        ]

        _LOGGER.debug(kaldi_cmd)

        with tempfile.NamedTemporaryFile(suffix=".wav", mode="wb") as temp_file:
            temp_file.write(wav_data)

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

            # Get result back as JSON
            result_json, _ = kaldi_proc.communicate()
            result = json.loads(result_json)

            # Empty string indicates failure
            text = str(result.get("text", ""))
            if len(text) > 0:
                return Transcription(
                    result=TranscriptionResult.SUCCESS,
                    text=text,
                    likelihood=float(result["likelihood"]),
                    decode_seconds=float(result["decode_seconds"]),
                )

            return Transcription(result=TranscriptionResult.FAILURE)


# -----------------------------------------------------------------------------


class JuliusTranscriber(Transcriber):
    """Speech to text with Julius."""

    def __init__(
        self,
        model_dir: Path,
        dictionary: Path,
        language_model: Path,
        debug: bool = False,
    ):
        self.model_dir = model_dir
        self.dictionary = dictionary
        self.language_model = language_model
        self.debug = debug

        self.julius_started = False
        self.julius_proc: Optional[subprocess.Popen] = None
        self.temp_dir: Optional[Path] = None
        self.julius_out: Optional[TextIO] = None

    def transcribe_wav(self, wav_data: bytes) -> Dict[str, Any]:
        if not self.julius_started:
            self.start_julius()

        # Write path to WAV file
        _LOGGER.debug("Sending %s byte(s) to Julius", len(wav_data))
        start_time = time.perf_counter()

        with tempfile.NamedTemporaryFile(suffix=".wav", mode="wb+") as temp_file:
            temp_file.write(wav_data)
            temp_file.seek(0)

            print(temp_file.name, file=self.julius_out)
            self.julius_out.flush()

            sentence_line = ""
            line = self.julius_in.readline().strip()
            _LOGGER.debug("Julius> %s", line)

            while True:
                if line.startswith("sentence1:"):
                    sentence_line = line.split(":", maxsplit=1)[1]
                    break

                if "error" in line.lower():
                    # Give up with an empty transcription
                    _LOGGER.warning(line)
                    break

                line = self.julius_in.readline().strip()
                _LOGGER.debug("Julius> %s", line)

            # Exclude <s> and </s>
            _LOGGER.debug(sentence_line)
            result_text = sentence_line.replace("<s>", "").replace("</s>", "").strip()
            end_time = time.time()

        # Empty string indicates failure
        text = result_text.strip()

        return {
            "text": result_text.strip(),
            "transcribe_seconds": end_time - start_time,
            "wav_seconds": wav_duration,
        }

    def stop(self):
        """Stop transcriber."""
        if self.julius_out is not None:
            # Close FIFO
            self.julius_out.close()
            self.julius_out = None

        if self.temp_dir is not None:
            # Delete temp directory
            self.temp_dir.cleanup()
            self.temp_dir = None

        if self.julius_proc is not None:
            # Terminate process
            _LOGGER.debug("Stopping Julius")
            self.julius_proc.terminate()
            self.julius_proc.wait()
            self.julius_proc = None
            _LOGGER.debug("Stopped Julius")

        self.julius_started = False

    def start_julius(self):
        """Create Julius process and run until started."""
        _LOGGER.debug("Starting Julius")
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

        if not self.debug:
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

        _LOGGER.debug(julius_cmd)

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

        _LOGGER.debug("Julius started")
