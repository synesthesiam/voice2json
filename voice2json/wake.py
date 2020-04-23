"""Methods for wake word detection."""
import argparse
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
    from precise_runner import PreciseEngine, PreciseRunner, ReadWriteStream

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

    _LOGGER.debug("Loading Precise (engine=%s, model=%s)", engine_path, model_path)
    engine = PreciseEngine(
        str(engine_path), str(model_path), chunk_size=args.chunk_size
    )

    assert engine, "Engine not loaded"

    # Patch get_prediction to avoid errors on exit
    _get_prediction = engine.get_prediction

    def safe_get_prediction(chunk):
        try:
            return _get_prediction(chunk)
        except ValueError:
            return 0.0

    engine.get_prediction = safe_get_prediction

    # Create stream to write audio chunks to
    engine_stream = ReadWriteStream()

    # Create runner
    _LOGGER.debug(
        "Creating Precise runner (sensitivity=%s, trigger_level=%s)",
        sensitivity,
        trigger_level,
    )

    if args.debug:

        def on_prediction(prob: float):
            _LOGGER.debug("Prediction: %s", prob)

    else:

        def on_prediction(prob: float):
            pass

    start_time = time.perf_counter()
    activation_count = 0

    def on_activation():
        nonlocal activation_count
        print_json(
            {
                "keyword": str(model_path),
                "detect_seconds": time.perf_counter() - start_time,
            }
        )
        activation_count += 1

    runner = PreciseRunner(
        engine,
        stream=engine_stream,
        sensitivity=sensitivity,
        trigger_level=trigger_level,
        on_activation=on_activation,
        on_prediction=on_prediction,
    )

    assert runner, "Runner not loaded"
    runner.start()

    # Create audio source and start listening
    audio_source = await core.make_audio_source(args.audio_source)

    try:
        while True:
            chunk = await audio_source.read(args.chunk_size)
            if chunk:
                engine_stream.write(chunk)
            else:
                _LOGGER.warning("Received empty audio chunk.")

            # Check exit count
            if (args.exit_count is not None) and (activation_count >= args.exit_count):
                break
    finally:
        try:
            await audio_source.close()
            runner.stop()
        except Exception:
            pass
