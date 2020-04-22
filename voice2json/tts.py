"""Text to speech methods for voice2json command-line interface."""
import argparse
import asyncio
import logging
import shlex
import sys
import typing

import pydash

from .core import Voice2JsonCore

_LOGGER = logging.getLogger("voice2json.tts")

# -----------------------------------------------------------------------------


async def speak_espeak(args: argparse.Namespace, core: Voice2JsonCore) -> None:
    """Speak one or more sentences using eSpeak."""
    voice = pydash.get(core.profile, "text-to-speech.espeak.voice")
    espeak_cmd_format = pydash.get(core.profile, "text-to-speech.espeak.speak-command")
    play_command = shlex.split(pydash.get(core.profile, "audio.play-command"))

    # Process sentence(s)
    if len(args.sentence) > 0:
        sentences = args.sentence
    else:
        sentences = sys.stdin

    for sentence in sentences:
        sentence = sentence.strip()
        espeak_cmd = shlex.split(espeak_cmd_format.format(sentence=sentence))
        espeak_cmd.append("--stdout")

        if voice is not None:
            espeak_cmd.extend(["-v", str(voice)])

        _LOGGER.debug(espeak_cmd)
        speak_process = await asyncio.create_subprocess_exec(
            *espeak_cmd, stdout=asyncio.subprocess.PIPE
        )
        wav_data, _ = await speak_process.communicate()

        if args.wav_sink is not None:
            # Write WAV output somewhere
            if args.wav_sink == "-":
                # STDOUT
                wav_sink = sys.stdout.buffer
            else:
                # File output
                wav_sink = open(args.wav_sink, "wb")

            wav_sink.write(wav_data)
            wav_sink.flush()
        else:
            _LOGGER.debug(play_command)

            # Speak sentence
            print(sentence)
            play_process = await asyncio.create_subprocess_exec(
                *play_command, stdin=asyncio.subprocess.PIPE
            )
            await play_process.communicate(input=wav_data)


async def speak_marytts(
    args: argparse.Namespace, core: Voice2JsonCore, marytts_voice: str
) -> None:
    """Speak one or more sentences using MaryTTS."""
    play_command = shlex.split(pydash.get(core.profile, "audio.play-command"))

    marytts_locale = pydash.get(
        core.profile,
        "text-to-speech.marytts.locale",
        pydash.get(core.profile, "language.code"),
    )
    marytts_url = str(
        pydash.get(
            core.profile,
            "text-to-speech.marytts.process-url",
            "http://localhost:59125/process",
        )
    )

    # Set up default params
    marytts_params: typing.Dict[str, str] = {
        "INPUT_TEXT": "",
        "INPUT_TYPE": "TEXT",
        "AUDIO": "WAVE",
        "OUTPUT_TYPE": "AUDIO",
        "VOICE": marytts_voice,
    }

    if marytts_locale is not None:
        marytts_params["LOCALE"] = marytts_locale

    # Process sentence(s)
    if args.sentence:
        sentences = args.sentence
    else:
        sentences = sys.stdin

    for sentence in sentences:
        sentence = sentence.strip()
        marytts_params["INPUT_TEXT"] = sentence

        # Do GET requests
        _LOGGER.debug("%s %s", marytts_url, marytts_params)
        async with core.http_session.get(
            marytts_url, params=marytts_params, ssl=core.ssl_context
        ) as response:
            data = await response.read()
            if response.status != 200:
                # Print error message
                _LOGGER.error(data.decode())

            response.raise_for_status()

            wav_data = data
            if args.wav_sink is not None:
                # Write WAV output somewhere
                if args.wav_sink == "-":
                    # STDOUT
                    wav_sink = sys.stdout.buffer
                else:
                    # File output
                    wav_sink = open(args.wav_sink, "wb")

                wav_sink.write(wav_data)
                wav_sink.flush()
            else:
                _LOGGER.debug(play_command)

                # Speak sentence
                print(sentence)
                play_process = await asyncio.create_subprocess_exec(
                    *play_command, stdin=asyncio.subprocess.PIPE
                )
                await play_process.communicate(input=wav_data)
