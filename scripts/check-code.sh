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

flake8 "${code_dir}"/*.py
pylint "${code_dir}"/*.py
mypy "${code_dir}"/*.py
black --check "${code_dir}"
isort --check-only "${code_dir}"/*.py

# -----------------------------------------------------------------------------

echo "OK"
