#!/usr/bin/env python3
import argparse
import collections
import logging
import platform
import subprocess
from pathlib import Path

import yaml

_LOGGER = logging.getLogger("verify_profile")


def main():
    parser = argparse.ArgumentParser(prog="verify-profile.py")
    parser.add_argument(
        "profile_yml", help="Path to profile YAML file with file details"
    )
    parser.add_argument("--profile-name", help="Override profile name from file")
    parser.add_argument("--url-format", help="Change url download format")
    parser.add_argument(
        "--machine", default=platform.machine(), help="Override platform.machine"
    )
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG messages to console"
    )
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    _LOGGER.debug(args)

    args.profile_yml = Path(args.profile_yml)

    if args.profile_name is None:
        args.profile_name = args.profile_yml.stem

    with open(args.profile_yml, "r") as profile_file:
        files_dict = yaml.safe_load(profile_file)

    url_format = files_dict["url_format"]

    if args.url_format:
        url_format = args.url_format

    for condition, files in files_dict.items():
        if not isinstance(files, collections.abc.Mapping):
            continue

        for file_path, file_info in files.items():
            try:
                url = url_format.format(
                    profile=args.profile_name, file=file_path, machine=args.machine
                )
                expected_size = int(file_info["bytes"])
                headers = (
                    subprocess.check_output(
                        ["curl", "--silent", "--location", "--head", url]
                    )
                    .decode()
                    .splitlines()
                )
                actual_size = None
                for header in headers:
                    header = header.strip()
                    if header:
                        if header.startswith("HTTP"):
                            assert header.split()[-1] in (
                                "200",
                                "302",
                            ), f"{url} {header}"
                            continue

                        header_name, header_value = header.split(":", maxsplit=1)
                        header_name = header_name.strip().lower()

                        if header_name == "content-length":
                            actual_size = int(header_value)

                if actual_size is None:
                    _LOGGER.error("%s (no size)", url)
                    continue

                if expected_size != actual_size:
                    _LOGGER.error(
                        "%s (wrong size, expected %s, got %s)",
                        file_path,
                        expected_size,
                        actual_size,
                    )
                    continue

                _LOGGER.debug("%s %s %s %s", file_path, url, expected_size, actual_size)
            except Exception as e:
                _LOGGER.exception("%s %s", file_path, file_info)
                raise e


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
