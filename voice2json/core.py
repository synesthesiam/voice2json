"""
Core voice2json command support.
"""
import asyncio
import io
import logging
import os
import queue
import shlex
import ssl
import sys
import threading
import typing
import wave
from pathlib import Path

import pydash

_LOGGER = logging.getLogger("voice2json.core")

# -----------------------------------------------------------------------------


class Voice2JsonCore:
    """Core voice2json command support."""

    def __init__(
        self,
        profile_file: Path,
        profile: typing.Dict[str, typing.Any],
        certfile: typing.Optional[str] = None,
        keyfile: typing.Optional[str] = None,
    ):
        """Initialize voice2json."""
        self.profile_file = profile_file
        self.profile_dir = profile_file.parent
        self.profile = profile

        # Shared aiohttp client session (enable SSL)
        self.ssl_context = ssl.SSLContext()
        if certfile:
            _LOGGER.debug("Using SSL certificate %s (keyfile=%s)", certfile, keyfile)
            self.ssl_context.load_cert_chain(certfile, keyfile)

        self._http_session = None

    @property
    def http_session(self):
        """Get or create async HTTP session."""
        import aiohttp

        if not self._http_session:
            self._http_session = aiohttp.ClientSession()

        return self._http_session

    # -------------------------------------------------------------------------
    # train-profile
    # -------------------------------------------------------------------------

    async def train_profile(self):
        """Generate speech/intent artifacts for a profile."""
        from . import train

        await train.train_profile(self.profile_dir, self.profile)

    # -------------------------------------------------------------------------
    # transcribe-wav
    # -------------------------------------------------------------------------

    def get_transcriber(self, open_transcription=False, debug=False):
        """Create Transcriber based on profile speech system."""
        from .train import AcousticModelType

        # Load settings
        acoustic_model_type = AcousticModelType(
            pydash.get(
                self.profile, "speech-to-text.acoustic-model-type", "pocketsphinx"
            ).lower()
        )

        if acoustic_model_type == AcousticModelType.POCKETSPHINX:
            # Pocketsphinx
            return self.get_pocketsphinx_transcriber(
                open_transcription=open_transcription, debug=debug
            )

        if acoustic_model_type == AcousticModelType.KALDI:
            # Kaldi
            return self.get_kaldi_transcriber(
                open_transcription=open_transcription, debug=debug
            )

        if acoustic_model_type == AcousticModelType.JULIUS:
            # Julius
            return self.get_julius_transcriber(
                open_transcription=open_transcription, debug=debug
            )

        if acoustic_model_type == AcousticModelType.DEEPSPEECH:
            # DeepSpeech
            return self.get_deepspeech_transcriber(
                open_transcription=open_transcription, debug=debug
            )

        raise ValueError(f"Unsupported acoustic model type: {acoustic_model_type}")

    def get_pocketsphinx_transcriber(self, open_transcription=False, debug=False):
        """Create Transcriber for Pocketsphinx."""
        from rhasspyasr_pocketsphinx import PocketsphinxTranscriber

        # Load settings
        acoustic_model = self.ppath("speech-to-text.acoustic-model", "acoustic_model")
        assert acoustic_model, "Missing acoustic model"

        if open_transcription:
            # Use base dictionary/language model
            dictionary = self.ppath(
                "speech-to-text.base-dictionary", "base_dictionary.txt"
            )

            language_model = self.ppath(
                "speech-to-text.base-language-model", "base_language_model.txt"
            )

        else:
            # Use custom dictionary/language model
            dictionary = self.ppath("speech-to-text.dictionary", "dictionary.txt")

            language_model = self.ppath(
                "speech-to-text.language-model", "language_model.txt"
            )

        assert dictionary and language_model, "Missing dictionary or language model"

        mllr_matrix = self.ppath(
            "speech-to-text.pocketsphinx.mllr-matrix", "mllr_matrix"
        )

        return PocketsphinxTranscriber(
            acoustic_model,
            dictionary,
            language_model,
            mllr_matrix=mllr_matrix,
            debug=debug,
        )

    def get_kaldi_transcriber(self, open_transcription=False, debug=False):
        """Create Transcriber for Kaldi."""
        from rhasspyasr_kaldi import KaldiCommandLineTranscriber, KaldiModelType

        # Load settings
        model_type = KaldiModelType(
            pydash.get(self.profile, "speech-to-text.kaldi.model-type")
        )

        acoustic_model = self.ppath("speech-to-text.acoustic-model", "acoustic_model")
        assert acoustic_model, "Missing acoustic model"

        if open_transcription:
            # Use base graph
            graph_dir = self.ppath("speech-to-text.kaldi.base-graph-directory") or (
                acoustic_model / "model" / "graph"
            )
        else:
            # Use custom graph
            graph_dir = self.ppath("speech-to-text.kaldi.graph-directory") or (
                acoustic_model / "graph"
            )

        # Use kaldi-decode script
        return KaldiCommandLineTranscriber(model_type, acoustic_model, graph_dir)

    def get_deepspeech_transcriber(self, open_transcription=False, debug=False):
        """Create Transcriber for DeepSpeech."""
        from rhasspyasr_deepspeech import DeepSpeechTranscriber

        # Load settings
        acoustic_model = self.ppath(
            "speech-to-text.acoustic-model", "model/output_graph.pbmm"
        )

        assert acoustic_model, "Missing acoustic model"

        if open_transcription:
            # Use base model
            scorer = self.ppath(
                "speech-to-text.deepspeech.base-scorer", "model/base.scorer"
            )
        else:
            # Use custom model
            scorer = self.ppath("speech-to-text.deepspeech.scorer", "scorer")

        assert scorer, "Missing language model or scorer"

        return DeepSpeechTranscriber(acoustic_model, scorer)

    def get_julius_transcriber(self, open_transcription=False, debug=False):
        """Create Transcriber for Julius."""
        from .julius import JuliusTranscriber

        # Load settings
        acoustic_model = self.ppath("speech-to-text.acoustic-model", "acoustic_model")
        assert acoustic_model, "Missing acoustic model"

        if open_transcription:
            # Use base dictionary/language model
            dictionary = self.ppath(
                "speech-to-text.base-dictionary", "base_dictionary.txt"
            )

            language_model = self.ppath(
                "speech-to-text.base-language-model", "base_language_model.bin"
            )
        else:
            # Use custom dictionary/language model
            dictionary = self.ppath("speech-to-text.dictionary", "dictionary.txt")

            language_model = self.ppath(
                "speech-to-text.language-model", "language_model.txt"
            )

        assert dictionary and language_model, "Missing dictionary or language model"

        return JuliusTranscriber(
            self, acoustic_model, dictionary, language_model, debug=debug
        )

    # -------------------------------------------------------------------------
    # record-command
    # -------------------------------------------------------------------------

    def get_command_recorder(self):
        """Get voice command recorder based on profile settings."""
        from rhasspysilence import WebRtcVadRecorder

        # Load settings
        vad_mode = int(pydash.get(self.profile, "voice-command.vad-mode", 3))
        min_seconds = float(
            pydash.get(self.profile, "voice-command.minimum-seconds", 1)
        )
        max_seconds = float(
            pydash.get(self.profile, "voice-command.maximum-seconds", 30)
        )
        speech_seconds = float(
            pydash.get(self.profile, "voice-command.speech-seconds", 0.3)
        )
        silence_seconds = float(
            pydash.get(self.profile, "voice-command.silence-seconds", 0.5)
        )
        before_seconds = float(
            pydash.get(self.profile, "voice-command.before-seconds", 0.5)
        )
        skip_seconds = float(pydash.get(self.profile, "voice-command.skip-seconds", 0))
        chunk_size = int(pydash.get(self.profile, "voice-command.chunk-size", 960))
        sample_rate = int(
            pydash.get(self.profile, "audio.format.sample-rate-hertz", 16000)
        )

        return WebRtcVadRecorder(
            vad_mode=vad_mode,
            sample_rate=sample_rate,
            chunk_size=chunk_size,
            min_seconds=min_seconds,
            max_seconds=max_seconds,
            speech_seconds=speech_seconds,
            silence_seconds=silence_seconds,
            before_seconds=before_seconds,
            skip_seconds=skip_seconds,
        )

    # -------------------------------------------------------------------------
    # Utilities
    # -------------------------------------------------------------------------

    def ppath(
        self, query: str, default: typing.Optional[str] = None
    ) -> typing.Optional[Path]:
        """Return path from profile or path relative to the profile directory."""
        result = pydash.get(self.profile, query)
        if result is None:
            if default is not None:
                result = self.profile_dir / Path(default)
        else:
            result = Path(result)

        return result

    async def convert_wav(self, wav_data: bytes) -> bytes:
        """Convert WAV data to expected audio format."""
        convert_cmd_str = pydash.get(
            self.profile,
            "audio.convert-command",
            "sox -t wav - -r 16000 -e signed-integer -b 16 -c 1 -t wav -",
        )
        convert_cmd = shlex.split(convert_cmd_str)
        _LOGGER.debug(convert_cmd)

        convert_proc = await asyncio.create_subprocess_exec(
            *convert_cmd, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE
        )

        converted_data, _ = await convert_proc.communicate(input=wav_data)

        return converted_data

    async def maybe_convert_wav(self, wav_data: bytes) -> bytes:
        """Convert WAV data to expected audio format if necessary."""
        expected_rate = int(
            pydash.get(self.profile, "audio.format.sample-rate-hertz", 16000)
        )
        expected_width = (
            int(pydash.get(self.profile, "audio.format.sample-width-bits", 16)) // 8
        )
        expected_channels = int(
            pydash.get(self.profile, "audio.format.channel-count", 1)
        )

        with io.BytesIO(wav_data) as wav_io:
            with wave.open(wav_io, "rb") as wav_file:
                rate, width, channels = (
                    wav_file.getframerate(),
                    wav_file.getsampwidth(),
                    wav_file.getnchannels(),
                )
                if (
                    (rate != expected_rate)
                    or (width != expected_width)
                    or (channels != expected_channels)
                ):
                    _LOGGER.debug(
                        "Got %s Hz, %s byte(s), %s channel(s). Needed %s Hz, %s byte(s), %s channel(s)",
                        rate,
                        width,
                        channels,
                        expected_rate,
                        expected_width,
                        expected_channels,
                    )

                    # Do conversion
                    if rate < expected_rate:
                        # Probably being given 8Khz audio
                        _LOGGER.warning(
                            "Upsampling audio from %s to %s Hz. Expect poor performance!",
                            rate,
                            expected_rate,
                        )

                    return await self.convert_wav(wav_data)

                # Return original data
                return wav_data

    def buffer_to_wav(self, buffer: bytes) -> bytes:
        """Wraps a buffer of raw audio data in a WAV"""
        rate = int(pydash.get(self.profile, "audio.format.sample-rate-hertz", 16000))
        width = int(pydash.get(self.profile, "audio.format.sample-width-bits", 16)) // 8
        channels = int(pydash.get(self.profile, "audio.format.channel-count", 1))

        with io.BytesIO() as wav_buffer:
            wav_file: wave.Wave_write = wave.open(wav_buffer, mode="wb")
            with wav_file:
                wav_file.setframerate(rate)
                wav_file.setsampwidth(width)
                wav_file.setnchannels(channels)
                wav_file.writeframesraw(buffer)

            return wav_buffer.getvalue()

    async def get_audio_source(self):
        """Start a recording subprocess for expected audio format."""
        record_cmd_str = pydash.get(
            self.profile,
            "audio.record-command",
            "arecord -q -r 16000 -c 1 -f S16_LE -t raw",
        )
        record_cmd = shlex.split(record_cmd_str)
        _LOGGER.debug(record_cmd)
        record_proc = await asyncio.create_subprocess_exec(
            record_cmd[0], *record_cmd[1:], stdout=asyncio.subprocess.PIPE
        )

        class FakeBinaryIO:
            """Terminate subprocess when closing stream."""

            def __init__(self, proc):
                self.proc = proc

            async def read(self, n):
                """Read n bytes from stream."""
                assert self.proc, "Process not running"
                return await self.proc.stdout.read(n)

            async def close(self):
                """Terminate process."""
                if self.proc:
                    _proc = self.proc
                    self.proc = None
                    _proc.terminate()
                    await _proc.wait()

        return FakeBinaryIO(record_proc)

    # -------------------------------------------------------------------------

    async def stop(self):
        """Stop core."""
        if self._http_session:
            await self._http_session.close()
            self._http_session = None

    # -------------------------------------------------------------------------

    def check_trained(self) -> bool:
        """True if profile is trained."""
        # Load settings
        intent_graph_path = self.ppath(
            "intent-recognition.intent-graph", "intent.pickle.gz"
        )

        missing = False
        for path in [intent_graph_path]:
            if not (path and path.exists()):
                missing = True
                break

        return not missing

    # -------------------------------------------------------------------------

    async def make_audio_source(self, audio_source: str) -> typing.Any:
        """Create an async audio source from command-line argument."""
        if audio_source is None:
            # Process source
            _LOGGER.debug("Recording raw 16-bit 16Khz mono audio")
            return await self.get_audio_source()

        if audio_source == "-":
            # Standard input source
            if os.isatty(sys.stdin.fileno()):
                print(
                    "Recording raw 16-bit 16Khz mono audio from stdin", file=sys.stderr
                )

            return AsyncStdinReader()

        # File source
        import aiofiles

        _LOGGER.debug("Recording raw 16-bit 16Khz mono audio from %s", audio_source)
        return await aiofiles.open(audio_source, "rb")


# -----------------------------------------------------------------------------


class AsyncStdinReader:
    """Wrap sys.stdin.buffer in an async reader."""

    def __init__(self, loop: typing.Optional[asyncio.AbstractEventLoop] = None):
        self.loop = loop or asyncio.get_event_loop()
        self.read_n_queue: "queue.Queue[int]" = queue.Queue()
        self.read_result_queue: "asyncio.Queue[bytes]" = asyncio.Queue()
        self.read_thread: typing.Optional[threading.Thread] = None

    async def read(self, n: int) -> bytes:
        """Some bytes from stdin buffer."""
        if not self.read_thread:
            self.read_thread = threading.Thread(target=self._read_stdin, daemon=True)
            self.read_thread.start()

        self.read_n_queue.put(n)
        data = await self.read_result_queue.get()
        return data

    async def close(self):
        """Shut down read thread."""
        self.read_n_queue.put(None)

        if self.read_thread:
            self.read_thread.join(timeout=0.5)
            self.read_thread = None

    def _read_stdin(self):
        """Get requests to read some number of bytes and process them."""
        n = self.read_n_queue.get()
        while n is not None:
            result = sys.stdin.buffer.read(n)
            self.loop.call_soon_threadsafe(self.read_result_queue.put_nowait, result)
            n = self.read_n_queue.get()
