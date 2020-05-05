"""Methods for wake word detection."""
import argparse
import asyncio
import logging
import shutil
import time
from pathlib import Path

import pydash

from .core import Voice2JsonCore
from .utils import print_json

_LOGGER = logging.getLogger("voice2json.wake")

# -----------------------------------------------------------------------------


async def wake(args: argparse.Namespace, core: Voice2JsonCore) -> None:
    """Wait for wake word in audio stream."""
    # from precise_runner import PreciseEngine, PreciseRunner, ReadWriteStream

    # loop = asyncio.get_event_loop()

    # Load settings
    engine_path = pydash.get(core.profile, "wake-word.precise.engine-executable")
    if not engine_path:
        engine_path = shutil.which("precise-engine")

    model_path = core.ppath("wake-word.precise.model-file", "precise/hey-mycroft-2.pb")
    sensitivity = float(pydash.get(core.profile, "wake-word.sensitivity", 0.5))
    trigger_level = int(pydash.get(core.profile, "wake-word.precise.trigger-level", 3))

    # Load Precise engine
    assert engine_path and model_path, "Missing engine or model path"
    engine_path = Path(engine_path)
    model_path = Path(model_path)

    assert engine_path.exists(), f"Engine does not exist at {engine_path}"
    assert model_path.exists(), f"Model does not exist at {model_path}"

    _LOGGER.debug(
        "Loading Precise (engine=%s, model=%s, chunk_size=%s)",
        engine_path,
        model_path,
        args.chunk_size,
    )

    precise_cmd = [str(engine_path), str(model_path), str(args.chunk_size)]
    engine_proc = await asyncio.create_subprocess_exec(
        *precise_cmd, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE
    )

    chunk_stream = engine_proc.stdin
    prob_stream = engine_proc.stdout
    assert chunk_stream and prob_stream, "Failed to connect engine streams"

    # Create detector
    _LOGGER.debug(
        "Creating Precise detector (sensitivity=%s, trigger_level=%s)",
        sensitivity,
        trigger_level,
    )

    detector = TriggerDetector(args.chunk_size, sensitivity, trigger_level)
    activation_count = 0
    chunks_left = 0

    start_time = time.perf_counter()

    # Create audio source and start listening
    audio_source = await core.make_audio_source(args.audio_source)

    async def write_chunks():
        nonlocal chunks_left

        while True:
            chunk = await audio_source.read(args.chunk_size)
            if chunk:
                chunk_stream.write(chunk)
                await chunk_stream.drain()
                chunks_left += 1
            else:
                _LOGGER.debug("Received empty audio chunk")

                # Ensure one more prediction
                chunk_stream.write(b"\0" * args.chunk_size)
                await chunk_stream.drain()
                break

    asyncio.create_task(write_chunks())

    try:
        while True:
            if args.exit_timeout is None:
                # No timeout
                prob_bytes = await prob_stream.readline()
            else:
                # With timeout
                prob_bytes = await asyncio.wait_for(
                    prob_stream.readline(), timeout=args.exit_timeout
                )

            prob_str = prob_bytes.decode().strip()
            _LOGGER.debug("Prediction: %s", prob_str)

            if detector.update(float(prob_str)):
                # Activation
                activation_count += 1
                print_json(
                    {
                        "keyword": str(model_path),
                        "detect_seconds": time.perf_counter() - start_time,
                    }
                )

            chunks_left -= 1
            if chunks_left <= 0:
                break

            # Check exit count
            if (args.exit_count is not None) and (activation_count >= args.exit_count):
                break
    finally:
        try:
            await audio_source.close()
            engine_proc.terminate()
            await engine_proc.wait()
            # runner.stop()
        except Exception:
            pass


# -----------------------------------------------------------------------------

# Taken from precise-runner
class TriggerDetector:
    """
    Reads predictions and detects activations
    This prevents multiple close activations from occurring when
    the predictions look like ...!!!..!!...
    """

    def __init__(self, chunk_size, sensitivity=0.5, trigger_level=3):
        self.chunk_size = chunk_size
        self.sensitivity = sensitivity
        self.trigger_level = trigger_level
        self.activation = 0

    def update(self, prob):
        # type: (float) -> bool
        """Returns whether the new prediction caused an activation"""
        chunk_activated = prob > 1.0 - self.sensitivity

        if chunk_activated or self.activation < 0:
            self.activation += 1
            has_activated = self.activation > self.trigger_level
            if has_activated or chunk_activated and self.activation < 0:
                self.activation = -(8 * 2048) // self.chunk_size

            if has_activated:
                return True
        elif self.activation > 0:
            self.activation -= 1
        return False
