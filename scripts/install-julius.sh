#!/usr/bin/env bash
julius="$1"
output="$2"

if [[ -z "${output}" ]]; then
    echo "Usage: install-julius.sh julius.tar.gz output-dir/"
    exit 1
fi

tar -C "${output}" -xvf "${julius}" julius
