#!/usr/bin/env bash
set -e

this_dir="$( cd "$( dirname "$0" )" && pwd )"
src_dir="$(realpath "${this_dir}/../..")"

expected='turn on the living room lamp'
actual="$(voice2json "$@" transcribe-wav "${src_dir}/etc/test/turn_on_living_room_lamp.wav" | jq -r .text)"

if [[ "${actual}" != "${expected}" ]]; then
    echo "Expected '${expected}' got '${actual}'"
    exit 1
fi
