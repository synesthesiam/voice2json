#!/usr/bin/env bash
set -e
precise="$1"
output="$2"

if [[ -z "${output}" ]]; then
    echo "Usage: install-precise.sh precise-engine.tar.gz output-dir/"
    exit 1
fi

mkdir -p "${output}/lib/precise"
tar -C "${output}/lib/precise" -xf "${precise}" --strip-components=1
ln -sf "${output}/lib/precise/precise-engine" "${output}/bin/precise-engine"
