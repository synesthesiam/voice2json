#!/usr/bin/env bash
this_dir="$( cd "$( dirname "$0" )" && pwd )"
venv="${this_dir}/.venv"

# -----------------------------------------------------------------------------
# Command-line Arguments
# -----------------------------------------------------------------------------

. "${this_dir}/etc/shflags"

DEFINE_boolean 'venv' true 'Ignore virtual environment'

FLAGS "$@" || exit $?
eval set -- "${FLAGS_ARGV}"

# -----------------------------------------------------------------------------

if [[ "${FLAGS_venv}" -eq "${FLAGS_TRUE}" && -d "${venv}" ]]; then
    echo "Using virtual environment at ${venv}"
    source "${venv}/bin/activate"
    export LD_LIBRARY_PATH="${venv}/lib:${LD_LIBRARY_PATH}"
    export spec_bin_dir="${venv}/bin"
    export spec_lib_dir="${venv}/lib"
    export spec_site_dir="${venv}/lib/python3.6/site-packages"
else
    # Assume system install
    export spec_bin_dir="/usr/local/bin"
    export spec_lib_dir="/usr/local/lib"
    export spec_site_dir="/usr/local/lib/python3.6/site-packages"
fi

if [[ -z "$1" ]]; then
    echo "No spec file given"
    exit 1
fi

CPU_ARCH="$(lscpu | awk '/^Architecture/{print $2}')"

pyinstaller\
    -y \
    --workpath "build_${CPU_ARCH}/voice2json" \
    --distpath "dist_${CPU_ARCH}/voice2json" \
    "$@"
