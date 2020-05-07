#!/usr/bin/env bash
set -e

if [[ -z "${PIP_INSTALL}" ]]; then
    PIP_INSTALL='install --upgrade'
fi

# Directory of *this* script
this_dir="$( cd "$( dirname "$0" )" && pwd )"
src_dir="$(realpath "${this_dir}/..")"

# -----------------------------------------------------------------------------

target_arch="$1"
if [[ -z "${target_arch}" ]]; then
    target_arch="$(bash "${src_dir}/architecture.sh")"
fi

if [[ -z "${venv}" ]]; then
    venv="${src_dir}/.venv"
fi

if [[ -z "${download}" ]]; then
    download="${src_dir}/download"
fi

# -----------------------------------------------------------------------------

if [[ ! -d "${venv}" ]]; then
    # Create virtual environment
    echo "Creating virtual environment at ${venv}"
    python3 -m venv "${venv}"
fi

source "${venv}/bin/activate"

# Directory where pre-compiled binaries will be installed
mkdir -p "${venv}/tools"

# Install Python dependencies
echo 'Installing Python dependencies'
pip3 ${PIP_INSTALL} pip
pip3 ${PIP_INSTALL} wheel setuptools

# Install local Rhasspy dependencies if available
grep '^rhasspy-' "${src_dir}/requirements.txt" | \
    xargs pip3 ${PIP_INSTALL} -f "${download}"

# Pocketsphinx
if [[ -s "${download}/pocketsphinx-python.tar.gz" ]]; then
    echo 'Installing pocketsphinx'
    # Only install if not already present in venv
    if [[ -z "$(pip3 freeze | grep '^pocketsphinx==0.1.15$')" ]]; then
        pip3 ${PIP_INSTALL} "${download}/pocketsphinx-python.tar.gz"
    fi
fi

# Opengrm
opengrm_file="${download}/opengrm-1.3.4-${target_arch}.tar.gz"
if [[ -n "$(command -v ngramcount)" ]]; then
    echo 'Installing Opengrm'
    "${src_dir}/scripts/install-opengrm.sh" \
        "${opengrm_file}" \
        "${venv}/tools"
fi

# Phonetisaurus
phonetisaurus_file="${download}/phonetisaurus-2019-${target_arch}.tar.gz"
if [[ -n "$(command -v phonetisaurus-apply)" ]]; then
    echo 'Installing Phonetisaurus'
    "${src_dir}/scripts/install-phonetisaurus.sh" \
        "${phonetisaurus_file}" \
        "${venv}/tools"
fi

# Kaldi
kaldi_file="${download}/kaldi-2020-${target_arch}.tar.gz"
if [[ -s "${kaldi_file}" ]]; then
    echo 'Installing Kaldi'
    "${src_dir}/scripts/install-kaldi.sh" \
        "${kaldi_file}" \
        "${venv}/tools"
fi

# Mycroft Precise
precise_file="${download}/precise-engine_0.3.0_${target_arch}.tar.gz"
if [[ -s "${precise_file}" ]]; then
    echo 'Installing Mycroft Precise'
    "${src_dir}/scripts/install-precise.sh" \
        "${precise_file}" \
        "${venv}/tools"
fi

# Mozilla DeepSpeech
deepspeech_file="${download}/native_client.${target_arch}.cpu.linux.0.6.1.tar.xz"
if [[ -s "${deepspeech_file}" ]]; then
    echo 'Installing DeepSpeech Native Client'
    "${src_dir}/scripts/install-deepspeech.sh" \
        "${deepspeech_file}" \
        "${venv}/tools"
fi

# KenLM
kenlm_file="${download}/kenlm-20200308_${target_arch}.tar.gz"
if [[ -s "${kenlm_file}" ]]; then
    echo 'Installing Kenlm'
    "${src_dir}/scripts/install-kenlm.sh" \
        "${kenlm_file}" \
        "${venv}/tools"
fi

# Julius
julius_file="${download}/julius-4.5_${target_arch}.tar.gz"
if [[ -s "${julius_file}" ]]; then
    echo 'Installing Julius'
    "${src_dir}/scripts/install-julius.sh" \
        "${julius_file}" \
        "${venv}/tools"
fi

echo 'Installing requirements'
pip3 ${PIP_INSTALL} -r requirements.txt

# Optional development requirements
echo 'Installing development requirements'
if [[ -f 'requirements_dev.txt' ]]; then
    pip3 ${PIP_INSTALL} -r requirements_dev.txt || \
        echo "Failed to install development requirements"
fi

# -----------------------------------------------------------------------------

echo "OK"
