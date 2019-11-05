#!/usr/bin/env bash
this_dir="$( cd "$( dirname "$0" )" && pwd )"
CPU_ARCH="$(lscpu | awk '/^Architecture/{print $2}')"

# -----------------------------------------------------------------------------
# Command-line Arguments
# -----------------------------------------------------------------------------

. "${this_dir}/etc/shflags"

DEFINE_string 'venv' "${this_dir}/.venv_${CPU_ARCH}" 'Path to create virtual environment'
DEFINE_string 'download-dir' "${this_dir}/download" 'Directory to cache downloaded files'
DEFINE_string 'build-dir' "${this_dir}/build_${CPU_ARCH}" 'Directory to build dependencies in'
DEFINE_boolean 'create' true 'Create a virtual environment'
DEFINE_boolean 'overwrite' true 'Overwrite existing virtual environment'
DEFINE_boolean 'kaldi' true 'Install Kaldi speech recognizer'
DEFINE_boolean 'julius' true 'Install Julius speech recognizer'
DEFINE_boolean 'runtime' true 'Install packages needed for building and running'
DEFINE_boolean 'python' true 'Install Python dependencies'
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

if [[ "${FLAGS_create}" -eq "${FLAGS_FALSE}" ]]; then
    no_create='true'
fi

if [[ "${FLAGS_overwrite}" -eq "${FLAGS_FALSE}" ]]; then
    no_overwrite='true'
fi

if [[ "${FLAGS_kaldi}" -eq "${FLAGS_FALSE}" ]]; then
    no_kaldi='true'
fi

if [[ "${FLAGS_julius}" -eq "${FLAGS_FALSE}" ]]; then
    no_julius='true'
fi

if [[ "${FLAGS_runtime}" -eq "${FLAGS_FALSE}" ]]; then
    no_runtime='true'
fi

if [[ "${FLAGS_python}" -eq "${FLAGS_FALSE}" ]]; then
    no_python='true'
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

# all of this is needed by kaldi for some dumb reason
if [[ -z "${no_kaldi}" ]]; then
    if [[ -z "$(which svn)" ]]; then
        echo "Installing subversion"
        install subversion
    fi

    if [[ -z "$(which git)" ]]; then
        echo "Installing git"
        install git
    fi

    if [[ -z "$(which sox)" ]]; then
        echo "Installing sox"
        install sox
    fi

    if [[ -z "$(which unzip)" ]]; then
        echo "Installing unzip"
        install unzip
    fi

    if [[ -z "$(which python2.7)" ]]; then
        echo "Installing Python 2.7"
        install python2.7
    fi
fi

# rsync
if [[ -z "$(which rsync)" ]]; then
    echo "Installing rsync"
    install rsync
fi

# -----------------------------------------------------------------------------
# Runtime Tools
# -----------------------------------------------------------------------------

if [[ -z "${no_runtime}" ]]; then
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

    # espeak-ng
    if [[ -z "$(which espeak-ng)" ]]; then
        echo "Installing espeak-ng"
        install espeak-ng
    fi

    # java
    if [[ -z "$(which java)" ]]; then
        echo "Install java"
        install default-jre-headless
    fi
fi

# -----------------------------------------------------------------------------
# Virtual environment
# -----------------------------------------------------------------------------

if [[ -z "${no_create}" ]]; then
    if [[ -d "${venv}" && -z "${no_overwrite}" ]]; then
        # Set up fresh virtual environment
        echo "Re-creating virtual environment at ${venv}"
        rm -rf "${venv}"

        python3 -m venv "${venv}"
    else
        echo "Using virtual environment at ${venv}"
    fi

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
# Download Dependencies
# -----------------------------------------------------------------------------

# Python-Pocketsphinx
pocketsphinx_file="${download_dir}/pocketsphinx-python.tar.gz"
if [[ ! -f "${pocketsphinx_file}" ]]; then
    pocketsphinx_url='https://github.com/synesthesiam/pocketsphinx-python/releases/download/v1.0/pocketsphinx-python.tar.gz'
    echo "Downloading pocketsphinx (${pocketsphinx_url})"
    download "${pocketsphinx_url}" "${pocketsphinx_file}"
fi

# OpenFST
openfst_dir="${build_dir}/openfst-1.6.9"
if [[ ! -d "${openfst_dir}/build" ]]; then
    openfst_file="${download_dir}/openfst-1.6.9.tar.gz"

    if [[ ! -f "${openfst_file}" ]]; then
        openfst_url='http://openfst.org/twiki/pub/FST/FstDownload/openfst-1.6.9.tar.gz'
        echo "Downloading openfst (${openfst_url})"
        download "${openfst_url}" "${openfst_file}"
    fi
fi

# Opengrm
opengrm_dir="${build_dir}/opengrm-ngram-1.3.4"
if [[ ! -d "${opengrm_dir}/build" ]]; then
    opengrm_file="${download_dir}/opengrm-ngram-1.3.4.tar.gz"

    if [[ ! -f "${opengrm_file}" ]]; then
        opengrm_url='http://www.opengrm.org/twiki/pub/GRM/NGramDownload/opengrm-ngram-1.3.4.tar.gz'
        echo "Downloading opengrm (${opengrm_url})"
        download "${opengrm_url}" "${opengrm_file}"
    fi
fi

# Phonetisaurus
phonetisaurus_dir="${build_dir}/phonetisaurus"
if [[ ! -d "${phonetisaurus_dir}/build" ]]; then
    phonetisaurus_file="${download_dir}/phonetisaurus-2019.tar.gz"

    if [[ ! -f "${phonetisaurus_file}" ]]; then
        phonetisaurus_url='https://github.com/synesthesiam/phonetisaurus-2019/releases/download/v1.0/phonetisaurus-2019.tar.gz'
        echo "Downloading phonetisaurus (${phonetisaurus_url})"
        download "${phonetisaurus_url}" "${phonetisaurus_file}"
    fi
fi

# Kaldi
kaldi_dir="${build_dir}/kaldi-master"
if [[ -z "${no_kaldi}" || ! -d "${kaldi_dir}" ]]; then
    install libatlas-base-dev libatlas3-base gfortran
    sudo ldconfig
    kaldi_file="${download_dir}/kaldi-2019.tar.gz"

    if [[ ! -f "${kaldi_file}" ]]; then
        kaldi_url='https://github.com/kaldi-asr/kaldi/archive/master.tar.gz'
        echo "Downloading kaldi (${kaldi_url})"
        download "${kaldi_url}" "${kaldi_file}"
    fi
fi

# Julius
julius_dir="${build_dir}/julius-master"
if [[ -z "${no_julius}" || ! -d "${julius_dir}" ]]; then
    install zlib1g-dev
    julius_file="${download_dir}/julius-2019.tar.gz"

    if [[ ! -f "${julius_file}" ]]; then
        julius_url='https://github.com/julius-speech/julius/archive/master.tar.gz'
        echo "Downloading julius (${julius_url})"
        download "${julius_url}" "${julius_file}"
    fi
fi

# -----------------------------------------------------------------------------
# openfst
# -----------------------------------------------------------------------------

if [[ ! -d "${openfst_dir}/build" ]]; then
    echo "Building openfst"
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
if [[ ! -d "${opengrm_dir}/build" ]]; then
    echo "Building opengrm"
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

if [[ ! -d "${phonetisaurus_dir}/build" ]]; then
    echo "Installing phonetisaurus"
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

if [[ ! -z "${no_kaldi}" || ! -f "${kaldi_dir}/src/online2bin/online2-wav-nnet3-latgen-faster" ]]; then
    echo "Installing kaldi"

    # armhf
    if [[ -f '/usr/lib/arm-linux-gnueabihf/libatlas.so' ]]; then
        # Kaldi install doesn't check here, despite in being in ldconfig
        export ATLASLIBDIR='/usr/lib/arm-linux-gnueabihf'
    fi

    # aarch64
    if [[ -f '/usr/lib/aarch64-linux-gnu/libatlas.so' ]]; then
        # Kaldi install doesn't check here, despite in being in ldconfig
        export ATLASLIBDIR='/usr/lib/aarch64-linux-gnu'
    fi

    tar -C "${build_dir}" -xf "${kaldi_file}" && \
        cp "${this_dir}/etc/linux_atlas_aarch64.mk" "${kaldi_dir}/src/makefiles/" && \
        patch "${kaldi_dir}/src/configure" "${this_dir}/etc/kaldi-src-configure.patch" && \
        cd "${kaldi_dir}/tools" && \
        DOWNLOAD_DIR="${download_dir}" make -j "${make_threads}" && \
        cd "${kaldi_dir}/src" &&
        ./configure --shared --mathlib=ATLAS && \
            make depend -j "${make_threads}" && \
            make -j "${make_threads}"
fi

# -----------------------------------------------------------------------------
# julius
# -----------------------------------------------------------------------------

if [[ ! -z "${no_julius}" || ! -f "${julius_dir}/julius/julius" ]]; then
    echo "Installing julius"
    tar -C "${build_dir}" -xf "${julius_file}"

    for d in jcontrol support adintool; 
    do
	    cp "${this_dir}/etc/config.guess" "${this_dir}/etc/config.sub" "${julius_dir}/${d}/"
    done

    cd "${julius_dir}" && \
	    ./configure --enable-words-int --enable-sp-segment && \
	    make -j "${make_threads}"
fi

cp "${julius_dir}/julius/julius" "${venv}/bin/"
cp "${julius_dir}/adintool/adintool" "${venv}/bin/"

# -----------------------------------------------------------------------------
# Python requirements
# -----------------------------------------------------------------------------

if [[ -z "${no_python}" ]]; then
    # Pocketsphinx for Python (no sound)
    python3 -m pip install "${pocketsphinx_file}"

    # Other requirements
    python3 -m pip install \
            --global-option=build_ext \
            --global-option="-I${venv}/include" \
            --global-option="-L${venv}/lib" \
            -r "${this_dir}/requirements.txt"

    # Kaldi extension
    cd "${this_dir}" && \
        python3 kaldi_setup.py install
fi

# -----------------------------------------------------------------------------

echo "OK"
