#!/usr/bin/env bash
set -e

this_dir="$( cd "$( dirname "$0" )" && pwd )"
src_dir="$(realpath "${this_dir}/../..")"

expected='would you please turn on the living room lamp'
actual="$(voice2json "$@" transcribe-wav --open "${src_dir}/etc/test/would_you_please_turn_on_living_room_lamp.wav" | jq -r .text)"

if [[ "${actual}" != "${expected}" ]]; then
    echo "Expected '${expected}' got '${actual}'"
    exit 1
fi
