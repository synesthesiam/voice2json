#!/usr/bin/env bash
set -e
julius="$1"
output="$2"

if [[ -z "${output}" ]]; then
    echo "Usage: install-julius.sh julius.tar.gz output-dir/"
    exit 1
fi

mkdir -p "${output}/bin"
tar -C "${output}/bin" -xf "${julius}"
