#!/usr/bin/env bash
this_dir="$( cd "$( dirname "$0" )" && pwd )"
profiles_dir="$(realpath "${this_dir}/../voice2json-profiles")"

if [[ ! -d "${profiles_dir}" ]]; then
    echo "Expected profiles at ${profiles_dir}"
    exit 1
fi

CPU_ARCH="$(python3 -c 'import platform; print(platform.machine())')"

# -----------------------------------------------------------------------------

# Create temporary directory to hold profiles
temp_dir="$(mktemp -d)"
function finish {
    rm -rf "${temp_dir}"
}

trap finish EXIT

# Copy profiles into temp directory
profiles=('english/en-us_pocketsphinx-cmu' 'english/en-us_kaldi-zamia')
args=()

for profile_dir in "${profiles[@]}";
do
    dest_dir="${temp_dir}/${profile_dir}"
    mkdir -p "${dest_dir}"

    cp -R "${profiles_dir}/${profile_dir}"/* "${dest_dir}/"
    args+=('-p' "${dest_dir}")
done

# -----------------------------------------------------------------------------

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

# -----------------------------------------------------------------------------

export PYTHONPATH="${this_dir}"
export PATH="${this_dir}/etc/bin:${this_dir}/bin:${PATH}"

python3 "${this_dir}/voice2json/test.py" \
        "${args[@]}"
