#!/usr/bin/env bash
this_dir="$( cd "$( dirname "$0" )" && pwd )"
profiles_dir="$(realpath "${this_dir}/../voice2json-profiles")"

if [[ ! -d "${profiles_dir}" ]]; then
    echo "Expected profiles at ${profiles_dir}"
    exit 1
fi

export voice2json_dir="$(realpath "${this_dir}")"
venv="${this_dir}/.venv"

if [[ -d "${venv}" ]]; then
    # Use virtual environment
    source "${venv}/bin/activate"
    export LD_LIBRARY_PATH="${venv}/lib:${LD_LIBRARY_PATH}"
    export PATH="${venv}/bin:${PATH}"
fi

# Add Kaldi to library path
if [[ -z "${kaldi_dir}" ]]; then
    kaldi_dir="${this_dir}/build_${CPU_ARCH}/kaldi-master"
fi

if [[ -d "${kaldi_dir}" ]]; then
    export LD_LIBRARY_PATH="${kaldi_dir}/src/lib:${kaldi_dir}/tools/openfst/lib:${LD_LIBRARY_PATH}"
fi

export PYTHONPATH="${this_dir}"
export PATH="${this_dir}/etc/bin:${this_dir}/bin:${PATH}"

python3 "${this_dir}/voice2json/test.py" \
        -p "${profiles_dir}/english/en-us_pocketsphinx-cmu" \
        -p "${profiles_dir}/english/en-us_kaldi-zamia"
