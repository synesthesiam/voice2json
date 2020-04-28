#!/usr/bin/env bash
set -e
kaldi="$1"
output="$2"

if [[ -z "${output}" ]]; then
    echo "Usage: install-kaldi.sh kaldi.tar.gz output-dir/"
    exit 1
fi

mkdir -p "${output}/lib/kaldi"
tar -C "${output}/lib/kaldi" -xf "${kaldi}" --strip-components=2
