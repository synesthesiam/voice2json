#!/usr/bin/env python3
import io
import re
import json
import argparse
import subprocess
import logging
import time
import shlex
import tempfile
import threading
import wave
import atexit
import base64
import asyncio
from uuid import uuid4
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, BinaryIO, List

import pydash
from quart import (
    Quart,
    request,
    render_template,
    send_from_directory,
    flash,
    send_file,
    jsonify,
)

# -----------------------------------------------------------------------------

profile_path: Optional[Path] = None
download_dir: Optional[Path] = None

# Quart application
app = Quart("voice2json", template_folder=Path("templates").absolute())
app.secret_key = str(uuid4())

logger = logging.getLogger("app_noprofile")
loop = asyncio.get_event_loop()

# -----------------------------------------------------------------------------


class Info:
    def __init__(
        self,
        description: str,
        version: str,
        accuracy_closed: int,
        speed_closed: int,
        accuracy_open: int,
        speed_open: int,
    ):
        self.version = version
        self.description = description
        self.accuracy_closed = accuracy_closed
        self.speed_closed = speed_closed
        self.accuracy_open = accuracy_open
        self.speed_open = speed_open

    def download_path(self, name, download_dir):
        return download_dir / f"{name}_v{self.version}.tar.gz"


PROFILES = {
    "German (Deutsch)": {
        "de-de": {
            "de_kaldi-zamia": Info("Kaldi TDNN Zamia", 1.0, 5, 3, 5, 3),
            "de_pocketsphinx-cmu": Info("Pocketsphinx CMU", 1.0, 5, 29, 5, 5),
        }
    },
    "English": {
        "en-us": {"en-us_pocketsphinx-cmu": Info("Pocketsphinx CMU", 1.0, 3, 36, 0, 6)}
    },
}

# -----------------------------------------------------------------------------


@app.route("/", methods=["GET", "POST"])
async def index():
    if request.method == "POST":
        form = await request.form
        for key in form:
            if key.startswith("download-"):
                profile_name = key.split("-", maxsplit=1)[1]
                await flash(f"Downloading {profile_name}", "info")
                break
            elif key.startswith("install-"):
                profile_name = key.split("-", maxsplit=1)[1]
                await install_profile(profile_name)
                await flash(f"Installed {profile_name}", "success")
                break

    return await render_template(
        "index_noprofile.html",
        profile_path=profile_path,
        download_dir=download_dir,
        profiles=PROFILES,
        sorted=sorted,
        range=range,
    )


# @app.route("/download")
# async def download():
#     return await render_template(
#         "download_noprofile.html",
#         profile_path=profile_path,
#         profiles=PROFILES,
#         sorted=sorted,
#         range=range,
#     )


# -----------------------------------------------------------------------------
# Static Routes
# -----------------------------------------------------------------------------


@app.route("/css/<path:filename>", methods=["GET"])
def css(filename):
    return send_from_directory("css", filename)


@app.route("/js/<path:filename>", methods=["GET"])
def js(filename):
    return send_from_directory("js", filename)


@app.route("/img/<path:filename>", methods=["GET"])
def img(filename):
    return send_from_directory("img", filename)


@app.errorhandler(Exception)
def handle_error(err) -> Tuple[str, int]:
    logger.exception(err)
    return (str(err), 500)


# -----------------------------------------------------------------------------


async def install_profile(name):
    profile_dir = profile_path
    if str(profile_dir).endswith(".yml"):
        profile_dir = profile_path.parent

    info = None
    for lang_profiles in PROFILES.values():
        for locale_profiles in lang_profiles.values():
            info = locale_profiles.get(name)
            if info is not None:
                break

        if info is not None:
            break

    assert info is not None, f"No profile named {name}"

    tar_gz_path = info.download_path(name, download_dir)
    command = ["tar", "-C", str(profile_dir), "-xvf", str(tar_gz_path)]
    logger.debug(command)

    profile_dir.mkdir(parents=True, exist_ok=True)
    await asyncio.create_subprocess_exec(
        *command
    )


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true", help="Enable DEBUG mode")
    parser.add_argument(
        "--http-port", type=int, default=5000, help="Web server port (default: 5000)"
    )
    parser.add_argument(
        "--http-host", default="127.0.0.1", help="Web server host (default: 127.0.0.1)"
    )
    parser.add_argument("--profile", required=True, help="Path to voice2json profile")
    parser.add_argument("--cache", required=True, help="Path to download cache")
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    logger.debug(args)

    profile_path = Path(args.profile)
    download_dir = Path(args.cache)

    # Start web server
    try:
        app.run(port=args.http_port, host=args.http_host, debug=args.debug)
    except KeyboardInterrupt:
        pass
