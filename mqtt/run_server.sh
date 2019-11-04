#!/usr/bin/env bash
this_dir="$( cd "$( dirname "$0" )" && pwd )"
venv="${this_dir}/.venv"

if [[ -d "${venv}" ]]; then
    source "${venv}/bin/activate"
fi

cd "${this_dir}" && \
    python3 app.py "$@"
