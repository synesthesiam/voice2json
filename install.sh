#!/usr/bin/env bash
this_dir="$( cd "$( dirname "$0" )" && pwd )"

# -----------------------------------------------------------------------------
# Command-line Arguments
# -----------------------------------------------------------------------------

. "${this_dir}/etc/shflags"

DEFINE_string 'venv' "${this_dir}/.venv" 'Path to create virtual environment'
DEFINE_string 'download-dir' "${this_dir}/download" 'Directory to cache downloaded files'
DEFINE_string 'build-dir' "${this_dir}/build" 'Directory to build dependencies in'
DEFINE_boolean 'no-create' false 'Do not re-create the virtual environment'
DEFINE_boolean 'no-kaldi' false 'Do not install Kaldi speech recognizer'
DEFINE_boolean 'no-runtime' false 'Only install packages needed for building'
DEFINE_integer 'make-threads' 4 'Number of threads to use with make' 'j'

FLAGS "$@" || exit $?
eval set -- "${FLAGS_ARGV}"

# -----------------------------------------------------------------------------
# Default Settings
# -----------------------------------------------------------------------------

set -e

venv="${FLAGS_venv}"
download_dir="${FLAGS_download_dir}"
build_dir="${FLAGS_build_dir}"

if [[ "${FLAGS_no_create}" -eq "${FLAGS_TRUE}" ]]; then
    no_create='true'
fi

if [[ "${FLAGS_no_kaldi}" -eq "${FLAGS_TRUE}" ]]; then
    no_kaldi='true'
fi

if [[ "${FLAGS_no_runtime}" -eq "${FLAGS_TRUE}" ]]; then
    no_runtime='true'
fi

make_threads="${FLAGS_make_threads}"

mkdir -p "${download_dir}"
mkdir -p "${build_dir}"

# -----------------------------------------------------------------------------
# Build Tools
# -----------------------------------------------------------------------------

function install {
    sudo apt-get install -y "$@"
}

function python_module {
    python3 -c "import $1" 2>/dev/null
    if [[ "$?" -eq "0" ]]; then
        echo "$1"
    fi
}

export -f python_module

function download {
    mkdir -p "$(dirname "$2")"
    curl -sSfL -o "$2" "$1"
    echo "$1 => $2"
}

# python 3
if [[ -z "$(which python3)" ]]; then
    echo "Installing python 3"
    install python3
fi

# pip
if [[ -z "$(python_module pip)" ]]; then
    echo "Installing python pip"
    install python3-pip
fi

# venv
if [[ -z "$(python_module venv)" ]]; then
    echo "Installing python venv"
    install python3-venv
fi

# python3-dev
if [[ -z "$(python_module distutils.sysconfig)" ]]; then
    echo "Installing python dev"
    install python3-dev
fi

# autotools
if [[ -z "$(which autoconf)" || -z "$(which automake)" || -z "$(which libtoolize)" ]]; then
    echo "Installing autotools"
    install autoconf automake libtool
fi

# bison
if [[ -z "$(which bison)" ]]; then
    echo "Installing bison"
    install bison
fi

# swig
if [[ -z "$(which swig)" ]]; then
    echo "Installing swig"
    install swig
fi

# curl
if [[ -z "$(which curl)" ]]; then
    echo "Installing curl"
    install curl
fi

# subversion (needed by kaldi for some dumb reason)
if [[ -z "${no_kaldi}" && -z "$(which svn)" ]]; then
    echo "Installing subversion"
    install subversion
fi

# -----------------------------------------------------------------------------
# Runtime Tools
# -----------------------------------------------------------------------------

if [[ -z "${no_runtime}" ]]; then
    # gstreamer
    if [[ -z "$(which gst-launch-1.0)" ]]; then
        echo "Installing gstreamer"
        install gstreamer1.0-pulseaudio gstreamer1.0-tools gstreamer1.0-plugins-good
    fi

    # jq
    if [[ -z "$(which jq)" ]]; then
        echo "Installing jq"
        install jq
    fi

    # sox
    if [[ -z "$(which sox)" ]]; then
        echo "Installing sox"
        install sox
    fi

    # espeak
    if [[ -z "$(which espeak)" ]]; then
        echo "Installing espeak"
        install espeak
    fi
fi

# -----------------------------------------------------------------------------
# Virtual environment
# -----------------------------------------------------------------------------

if [[ -z "${no_create}" ]]; then
    # Set up fresh virtual environment
    echo "Re-creating virtual environment at ${venv}"
    rm -rf "${venv}"

    python3 -m venv "${venv}"
    source "${venv}/bin/activate"
    python3 -m pip install wheel
elif [[ -d "${venv}" ]]; then
    echo "Using virtual environment at ${venv}"
    source "${venv}/bin/activate"
else
    echo "Not using a virtual environment"
    venv='/usr'
fi

# -----------------------------------------------------------------------------
# Pocketsphinx for Python (no sound)
# -----------------------------------------------------------------------------

pocketsphinx_file="${download_dir}/pocketsphinx-python.tar.gz"
if [[ ! -f "${pocketsphinx_file}" ]]; then
    pocketsphinx_url='https://github.com/synesthesiam/pocketsphinx-python/releases/download/v1.0/pocketsphinx-python.tar.gz'
    echo "Downloading pocketsphinx (${pocketsphinx_url})"
    download "${pocketsphinx_url}" "${pocketsphinx_file}"
fi

python3 -m pip install "${pocketsphinx_file}"

# -----------------------------------------------------------------------------
# openfst
# -----------------------------------------------------------------------------

openfst_dir="${build_dir}/openfst-1.6.9"
if [[ ! -d "${openfst_dir}/build" ]]; then
    echo "Building openfst"
    openfst_file="${download_dir}/openfst-1.6.9.tar.gz"

    if [[ ! -f "${openfst_file}" ]]; then
        openfst_url='http://openfst.org/twiki/pub/FST/FstDownload/openfst-1.6.9.tar.gz'
        echo "Downloading openfst (${openfst_url})"
        download "${openfst_url}" "${openfst_file}"
    fi

    tar -C "${build_dir}" -xf "${openfst_file}" && \
        cd "${openfst_dir}" && \
        ./configure "--prefix=${openfst_dir}/build" --enable-far --enable-static --enable-shared --enable-ngram-fsts && \
        make -j "${make_threads}" && \
        make install
fi

# Copy build artifacts into virtual environment
cp -R "${openfst_dir}"/build/bin/* "${venv}/bin/"
cp -R "${openfst_dir}"/build/include/* "${venv}/include/"
cp -R "${openfst_dir}"/build/lib/*.so* "${venv}/lib/"

# -----------------------------------------------------------------------------
# opengrm
# -----------------------------------------------------------------------------

# opengrm
opengrm_dir="${build_dir}/opengrm-ngram-1.3.4"
if [[ ! -d "${opengrm_dir}/build" ]]; then
    echo "Building opengrm"
    opengrm_file="${download_dir}/opengrm-ngram-1.3.4.tar.gz"

    if [[ ! -f "${opengrm_file}" ]]; then
        opengrm_url='http://www.opengrm.org/twiki/GRM/NGramDownload/opengrm-ngram-1.3.4.tar.gz'
        echo "Downloading opengrm (${opengrm_url})"
        download "${opengrm_url}" "${opengrm_file}"
    fi

    tar -C "${build_dir}" -xf "${opengrm_file}" && \
        cd "${opengrm_dir}" && \
        CXXFLAGS="-I${venv}/include" LDFLAGS="-L${venv}/lib" ./configure "--prefix=${opengrm_dir}/build" && \
        make -j "${make_threads}" && \
        make install
fi

# Copy build artifacts into virtual environment
cp -R "${opengrm_dir}"/build/bin/* "${venv}/bin/"
cp -R "${opengrm_dir}"/build/include/* "${venv}/include/"
cp -R "${opengrm_dir}"/build/lib/*.so* "${venv}/lib/"

# -----------------------------------------------------------------------------
# phonetisaurus
# -----------------------------------------------------------------------------

phonetisaurus_dir="${build_dir}/phonetisaurus"
if [[ ! -d "${phonetisaurus_dir}/build" ]]; then
    echo "Installing phonetisaurus"
    phonetisaurus_file="${download_dir}/phonetisaurus-2019.tar.gz"

    if [[ ! -f "${phonetisaurus_file}" ]]; then
        phonetisaurus_url='https://github.com/synesthesiam/phonetisaurus-2019/releases/download/v1.0/phonetisaurus-2019.tar.gz'
        echo "Downloading phonetisaurus (${phonetisaurus_url})"
        download "${phonetisaurus_url}" "${phonetisaurus_file}"
    fi

    tar -C "${build_dir}" -xf "${phonetisaurus_file}" && \
        cd "${phonetisaurus_dir}" && \
        ./configure "--prefix=${phonetisaurus_dir}/build" \
                    --with-openfst-includes="${venv}/include" \
                    --with-openfst-libs="${venv}/lib" && \
        make -j "${make_threads}" && \
        make install
fi

# Copy build artifacts into virtual environment
cp -R "${phonetisaurus_dir}"/build/bin/* "${venv}/bin/"

# -----------------------------------------------------------------------------
# kaldi
# -----------------------------------------------------------------------------

kaldi_dir="${build_dir}/kaldi-master"
if [[ ! -z "${no_kaldi}" || ! -d "${kaldi_dir}/build" ]]; then
    echo "Installing kaldi"
    install libatlas-base-dev libatlas3-base
    kaldi_file="${download_dir}/kaldi-2019.tar.gz"

    if [[ ! -f "${kaldi_file}" ]]; then
        kaldi_url='https://github.com/kaldi-asr/kaldi/archive/master.tar.gz'
        echo "Downloading kaldi (${kaldi_url})"
        download "${kaldi_url}" "${kaldi_file}"
    fi

    tar -C "${build_dir}" -xf "${kaldi_file}" && \
        cd "${kaldi_dir}/tools" && \
        make -j "${make_threads}" && \
        cd "${kaldi_dir}/src" &&
        ./configure --shared --mathlib=ATLAS && \
        make depend -j "${make_threads}" && \
        make -j "${make_threads}"
fi

# -----------------------------------------------------------------------------
# Python requirements
# -----------------------------------------------------------------------------

python3 -m pip install \
        --global-option=build_ext --global-option="-L${venv}/lib" \
        -r "${this_dir}/requirements.txt"

# -----------------------------------------------------------------------------

echo "OK"
