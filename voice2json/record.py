"""Recording methods."""
import argparse
import asyncio
import dataclasses
import gzip
import itertools
import logging
import os
import re
import sys
import typing
from pathlib import Path

import aioconsole
import jsonlines

from .core import Voice2JsonCore
from .utils import dag_paths_random, itershuffle, print_json

_LOGGER = logging.getLogger("voice2json.record")

# -----------------------------------------------------------------------------


async def record_command(args: argparse.Namespace, core: Voice2JsonCore) -> None:
    """Segment audio by speech and silence."""
    import rhasspysilence

    # Make sure profile has been trained
    assert core.check_trained(), "Not trained"

    # Expecting raw 16-bit, 16Khz mono audio
    audio_source = await core.make_audio_source(args.audio_source)

    # JSON events are not printed by default
    json_file = None
    wav_sink = sys.stdout.buffer

    if (args.wav_sink is not None) and (args.wav_sink != "-"):
        wav_sink = open(args.wav_sink, "wb")

        # Print JSON to stdout
        json_file = sys.stdout

    # Record command
    try:
        recorder = core.get_command_recorder()
        recorder.start()

        result: typing.Optional[rhasspysilence.VoiceCommand] = None

        # Read raw audio chunks
        chunk = await audio_source.read(args.chunk_size)
        while chunk:
            result = recorder.process_chunk(chunk)
            if result:
                # Voice command finished
                break

            chunk = await audio_source.read(args.chunk_size)

        try:
            await audio_source.close()
        except Exception:
            _LOGGER.exception("close audio")

        # Output WAV data
        if result:
            result.audio_data = result.audio_data or bytes()
            wav_bytes = core.buffer_to_wav(result.audio_data)

            if args.output_size:
                # Write size first on a separate line
                size_str = str(len(wav_bytes)) + "\n"
                wav_sink.write(size_str.encode())

            wav_sink.write(wav_bytes)

            if json_file:
                for event in result.events:
                    print_json(dataclasses.asdict(event), out_file=json_file)
    except KeyboardInterrupt:
        pass  # expected


# -----------------------------------------------------------------------------


async def record_examples(args: argparse.Namespace, core: Voice2JsonCore) -> None:
    """Record example voice commands."""
    import networkx as nx
    import rhasspynlu

    # Make sure profile has been trained
    assert core.check_trained(), "Not trained"

    chunk_size = args.chunk_size

    if args.directory:
        examples_dir = Path(args.directory)
    else:
        examples_dir = Path.cwd()
        if os.isatty(sys.stdin.fileno()):
            print("Examples will be saved to current directory", file=sys.stderr)

    examples_dir.mkdir(parents=True, exist_ok=True)

    # Load settings
    intent_graph_path = core.ppath(
        "intent-recognition.intent-graph", "intent.pickle.gz"
    )

    # Load intent graph
    _LOGGER.debug("Loading %s", intent_graph_path)
    with gzip.GzipFile(intent_graph_path, mode="rb") as graph_gzip:
        intent_graph = nx.readwrite.gpickle.read_gpickle(graph_gzip)

    start_node, end_node = rhasspynlu.jsgf_graph.get_start_end_nodes(intent_graph)
    assert (start_node is not None) and (
        end_node is not None
    ), "Missing start/end node(s)"

    # Iterable that yields random paths through the graph forever
    random_paths = itertools.cycle(
        itershuffle(dag_paths_random(intent_graph, start_node, end_node))
    )

    def generate_intent() -> typing.Dict[str, typing.Any]:
        # Generate sample intent
        path = next(random_paths)
        _, recognition = rhasspynlu.fsticuffs.path_to_recognition(path, intent_graph)
        assert recognition, "Path to recognition failed"
        return dataclasses.asdict(recognition)

    def get_wav_path(text: str, count: int) -> Path:
        # /dir/the_transcription_text-000.wav
        text = re.sub(r"\s+", "_", text)
        return examples_dir / f"{text}-{count:03d}.wav"

    # Expecting raw 16-bit, 16Khz mono audio
    audio_source = await core.make_audio_source(args.audio_source)

    # Recording task method
    audio_data = bytes()
    recording = False

    async def record_audio(audio_source, chunk_size: int) -> bytes:
        """Records audio until cancelled."""
        nonlocal recording, audio_data
        while True:
            chunk = await audio_source.read(chunk_size)
            if chunk and recording:
                audio_data += chunk

    record_task = asyncio.create_task(record_audio(audio_source, chunk_size))

    try:
        while True:
            # Generate random intent for prompt
            random_intent = generate_intent()
            text = random_intent["text"]

            # Prompt
            print("---")
            print(text)

            # Instructions
            print("Press ENTER to start recording (CTRL+C to exit)")
            await aioconsole.ainput()

            # Record
            audio_data = bytes()
            recording = True

            # Instructions
            print("Recording from audio source. Press ENTER to stop (CTRL+C to exit).")
            await aioconsole.ainput()

            # Save WAV
            recording = False
            logging.debug("Recorded %s byte(s) of audio data", len(audio_data))

            count = 0
            wav_path = get_wav_path(text, count)
            while wav_path.exists():
                # Find unique name
                count += 1
                wav_path = get_wav_path(text, count)

            wav_bytes = core.buffer_to_wav(audio_data)
            wav_path.write_bytes(wav_bytes)

            # Save transcription
            transcript_path = examples_dir / f"{wav_path.stem}.txt"
            transcript_path.write_text(text)

            # Save intent
            intent_path = examples_dir / f"{wav_path.stem}.json"
            with open(intent_path, "w") as intent_file:
                with jsonlines.Writer(intent_file) as out:
                    # pylint: disable=E1101
                    out.write(random_intent)

            # Response
            print("Wrote", wav_path)
            print("")

    except KeyboardInterrupt:
        pass
    finally:
        # input_event.set()
        record_task.cancel()

        try:
            await audio_source.close()
        except Exception:
            pass
