#!/usr/bin/env bash
set -e

# Directory of *this* script
this_dir="$( cd "$( dirname "$0" )" && pwd )"
src_dir="$(realpath "${this_dir}/..")"

venv="${src_dir}/.venv"
if [[ -d "${venv}" ]]; then
    source "${venv}/bin/activate"
fi

code_dir="${src_dir}/voice2json"

# -----------------------------------------------------------------------------

black "${code_dir}"
isort "${code_dir}"/*.py

# -----------------------------------------------------------------------------

echo "OK"
