#!/usr/bin/env bash
set -e
native_client="$1"
output="$2"

if [[ -z "${output}" ]]; then
    echo "Usage: install-deepspeech.sh native_client.tar.xz output-dir/"
    exit 1
fi

# -----------------------------------------------------------------------------

# Create a temporary directory for extraction
temp_dir="$(mktemp -d)"

function cleanup {
    rm -rf "${temp_dir}"
}

trap cleanup EXIT

# -----------------------------------------------------------------------------

tar -C "${temp_dir}" -xf "${native_client}"
install -D "--target-directory=${output}/bin" -- "${temp_dir}/generate_trie" "${temp_dir}/deepspeech"
install -D "--target-directory=${output}/lib" -- "${temp_dir}"/*.so*
install -D "--target-directory=${output}/include" -- "${temp_dir}"/*.h
