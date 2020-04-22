"""Methods for wake word detection."""
import argparse
import logging

from .core import Voice2JsonCore

_LOGGER = logging.getLogger("voice2json.wake")

# -----------------------------------------------------------------------------


async def wake(args: argparse.Namespace, core: Voice2JsonCore) -> None:
    """Wait for wake word in audio stream."""


#     # Expecting raw 16-bit, 16Khz mono audio
#     if args.audio_source is None:
#         audio_source = core.get_audio_source()
#         _LOGGER.debug("Recording raw 16-bit 16Khz mono audio")
#     elif args.audio_source == "-":
#         audio_source = sys.stdin.buffer
#         _LOGGER.debug("Recording raw 16-bit 16Khz mono audio from stdin")
#     else:
#         audio_source: typing.BinaryIO = open(args.audio_source, "rb")
#         _LOGGER.debug(
#             "Recording raw 16-bit 16Khz mono audio from %s", args.audio_source
#         )

#     try:
#         detector = core.get_wake_detector()

#         async for detection in detector.detect(audio_source):
#             print_json(attr.asdict(detection))

#             # Check exit count
#             if args.exit_count is not None:
#                 args.exit_count -= 1
#                 if args.exit_count <= 0:
#                     break
#     except KeyboardInterrupt:
#         pass  # expected
