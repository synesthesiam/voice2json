#!/usr/bin/env bash
set -e
kenlm="$1"
output="$2"

if [[ -z "${output}" ]]; then
    echo "Usage: install-kenlm.sh kenlm.tar.gz output-dir/"
    exit 1
fi

mkdir -p "${output}/bin"
tar -C "${output}/bin" -xf "${kenlm}"
