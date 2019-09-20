#!/usr/bin/env bash
this_dir="$( cd "$( dirname "$0" )" && pwd )"
venv="${this_dir}/.venv"

if [[ -d "${venv}" ]]; then
    # Use virtual environment
    source "${venv}/bin/activate"
    export LD_LIBRARY_PATH="${venv}/lib:${LD_LIBRARY_PATH}"
    export PATH="${venv}/bin:${PATH}"
fi

# Check to see if sphinxtrain is installed (pocketsphinx acoustic model tuning)
if [[ -d '/usr/lib/sphinxtrain' ]]; then
    export PATH="/usr/lib/sphinxtrain:${PATH}"
fi

export PYTHONPATH="${this_dir}"
export PATH="${this_dir}/bin:${PATH}"

python3 -m voice2json "$@"
