#!/usr/bin/env bash
set -e

this_dir="$( cd "$( dirname "$0" )" && pwd )"
src_dir="$(realpath "${this_dir}/../..")"

expected='ChangeLightState'
actual="$(voice2json "$@" recognize-intent --text 'turn on the living room lamp' | jq -r .intent.name)"

if [[ "${actual}" != "${expected}" ]]; then
    echo "Expected '${expected}' got '${actual}'"
    exit 1
fi
