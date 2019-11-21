"""Support for wake/hot word detection."""
import asyncio
import logging
import time
import struct
from pathlib import Path
from typing import Optional, BinaryIO

from voice2json.wake.porcupine import Porcupine
from voice2json.wake.const import WakeWordDetector, WakeWordDetection

_LOGGER = logging.getLogger(__name__)

# -----------------------------------------------------------------------------


class PorcupineDetector(WakeWordDetector):
    """Detect wake/hot words with porcupine."""

    def __init__(
        self,
        library_path: Path,
        params_path: Path,
        keyword_path: Path,
        sensitivity: float = 0.5,
    ):
        self.library_path = library_path
        self.params_path = params_path
        self.keyword_path = keyword_path
        self.sensitivity = sensitivity
        self.handle: Optional[Porcupine] = None

    async def detect(self, audio_source: BinaryIO) -> WakeWordDetection:
        """Detect wake word in audio stream."""
        # Load porcupine
        if self.handle is None:
            _LOGGER.debug("Loading porcupine")
            self.handle = Porcupine(
                str(self.library_path),
                str(self.params_path),
                keyword_file_paths=[str(self.keyword_path)],
                sensitivities=[self.sensitivity],
            )

        chunk_size = self.handle.frame_length * 2
        chunk_format = "h" * self.handle.frame_length

        async def async_chunks():
            while True:
                chunk = audio_source.read(chunk_size)
                if chunk:
                    if len(chunk) == chunk_size:
                        yield chunk
                    else:
                        # Avoid 100% CPU
                        asyncio.sleep(0.01)
                else:
                    break

        # Read first audio chunk
        start_time = time.perf_counter()
        chunk = audio_source.read(chunk_size)

        # Process audio chunks
        async for chunk in async_chunks():
            # Process audio chunk
            unpacked_chunk = struct.unpack_from(chunk_format, chunk)
            keyword_index = self.handle.process(unpacked_chunk)

            if keyword_index:
                yield WakeWordDetection(
                    keyword=str(self.keyword_path),
                    time=(time.perf_counter() - start_time),
                )
