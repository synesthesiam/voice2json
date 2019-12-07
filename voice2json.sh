#!/usr/bin/env bash
this_dir="$( cd "$( dirname "$0" )" && pwd )"
CPU_ARCH="$(python3 -c 'import platform; print(platform.machine())')"
export voice2json_dir="$(realpath "${this_dir}")"

venv="${this_dir}/.venv_${CPU_ARCH}"

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

# Add Kaldi to library path
if [[ -z "${kaldi_dir}" ]]; then
    kaldi_dir="${this_dir}/build_${CPU_ARCH}/kaldi-master"
fi

if [[ -d "${kaldi_dir}" ]]; then
    export LD_LIBRARY_PATH="${kaldi_dir}/src/lib:${kaldi_dir}/tools/openfst/lib:${LD_LIBRARY_PATH}"
fi

export PYTHONPATH="${this_dir}"
export PATH="${this_dir}/bin:${PATH}"

python3 -m voice2json "$@"
