#!/usr/bin/env bash
this_dir="$( cd "$( dirname "$0" )" && pwd )"

if [[ -z "${voice2json_dir}" ]]; then
    voice2json_dir="$(realpath "${this_dir}/..")"
fi

venv="${this_dir}/.venv"

if [[ -d "${venv}" ]]; then
    source "${venv}/bin/activate"
fi

export voice2json_profile=''

export PYTHONPATH="${voice2json_dir}:${PYTHONPATH}"
supervisord --config "${this_dir}/supervisord.conf"
