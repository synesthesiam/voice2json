"""Word pronunciation methods for voice2json."""
import argparse
import asyncio
import io
import logging
import shlex
import typing
from xml.etree import ElementTree as etree

import pydash

from .core import Voice2JsonCore

_LOGGER = logging.getLogger("voice2json.pronounce")


def get_pronounce_espeak(
    args: argparse.Namespace, core: Voice2JsonCore
) -> typing.Callable[
    [str, typing.Iterable[str]], typing.Coroutine[typing.Any, typing.Any, bytes]
]:
    """Get pronounce method for eSpeak."""
    # Use eSpeak
    espeak_voice = pydash.get(core.profile, "text-to-speech.espeak.voice")
    espeak_map_path = core.ppath(
        "text-to-speech.espeak.phoneme-map", "espeak_phonemes.txt"
    )

    assert (
        espeak_map_path and espeak_map_path.exists()
    ), f"Missing eSpeak phoneme map at {espeak_map_path}"

    espeak_phoneme_map: typing.Dict[str, str] = {}

    with open(espeak_map_path, "r") as map_file:
        for line in map_file:
            line = line.strip()
            if line:
                parts = line.split(maxsplit=1)
                espeak_phoneme_map[parts[0]] = parts[1]

    espeak_cmd_format = pydash.get(
        core.profile, "text-to-speech.espeak.pronounce-command"
    )

    async def do_pronounce(word: str, dict_phonemes: typing.Iterable[str]) -> bytes:
        espeak_phonemes = [espeak_phoneme_map[p] for p in dict_phonemes]
        espeak_str = "".join(espeak_phonemes)
        espeak_cmd = shlex.split(espeak_cmd_format.format(phonemes=espeak_str))

        if espeak_voice is not None:
            espeak_cmd.extend(["-v", str(espeak_voice)])

        _LOGGER.debug(espeak_cmd)
        process = await asyncio.create_subprocess_exec(
            *espeak_cmd, stdout=asyncio.subprocess.PIPE
        )
        stdout, _ = await process.communicate()
        return stdout

    return do_pronounce


def get_pronounce_marytts(
    args: argparse.Namespace, core: Voice2JsonCore, marytts_voice: str
) -> typing.Callable[
    [str, typing.Iterable[str]], typing.Coroutine[typing.Any, typing.Any, bytes]
]:
    """Get pronounce method for MaryTTS."""
    marytts_map_path = core.ppath(
        "text-to-speech.marytts.phoneme-map", "marytts_phonemes.txt"
    )

    assert (
        marytts_map_path and marytts_map_path.exists()
    ), "Missing MaryTTS phoneme map at {marytts_map_path}"

    marytts_phoneme_map: typing.Dict[str, str] = {}

    with open(marytts_map_path, "r") as map_file:
        for line in map_file:
            line = line.strip()
            if line:
                parts = line.split(maxsplit=1)
                marytts_phoneme_map[parts[0]] = parts[1]

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
        "AUDIO": "WAVE",
        "OUTPUT_TYPE": "AUDIO",
        "VOICE": marytts_voice,
    }

    if marytts_locale:
        marytts_params["LOCALE"] = marytts_locale

    # End of sentence token
    sentence_end = pydash.get(core.profile, "text-to-speech.marytts.sentence-end", "")

    # Rate of pronunciation
    pronounce_rate = str(
        pydash.get(core.profile, "text-to-speech.marytts.pronounce-rate", "5%")
    )

    async def do_pronounce(word: str, dict_phonemes: typing.Iterable[str]) -> bytes:
        marytts_phonemes = [marytts_phoneme_map[p] for p in dict_phonemes]
        phoneme_str = " ".join(marytts_phonemes)
        _LOGGER.debug(phoneme_str)

        # Construct MaryXML input
        mary_xml = etree.fromstring(
            """<?xml version="1.0" encoding="UTF-8"?>
        <maryxml version="0.5" xml:lang="en-US">
        <p><prosody rate="100%"><s><phrase></phrase></s></prosody></p>
        </maryxml>"""
        )

        s = next(mary_xml.iter())
        p = next(s.iter())
        p.attrib["rate"] = pronounce_rate

        phrase = next(iter(p.iter()))
        t = etree.SubElement(phrase, "t", attrib={"ph": phoneme_str})
        t.text = word

        if len(sentence_end) > 0:
            # Add end of sentence token
            eos = etree.SubElement(phrase, "t", attrib={"pos": "."})
            eos.text = sentence_end

        # Serialize XML
        with io.BytesIO() as xml_file:
            etree.ElementTree(mary_xml).write(
                xml_file, encoding="utf-8", xml_declaration=True
            )

            xml_string = xml_file.getvalue().decode()
            request_params = {
                "INPUT_TYPE": "RAWMARYXML",
                "INPUT_TEXT": xml_string,
                **marytts_params,
            }

        _LOGGER.debug("%s %s", marytts_url, request_params)

        async with core.http_session.get(
            marytts_url, params=request_params, ssl=core.ssl_context
        ) as response:
            data = await response.read()
            if response.status != 200:
                # Print error message
                _LOGGER.error(data.decode())

            response.raise_for_status()
            return data

    return do_pronounce
