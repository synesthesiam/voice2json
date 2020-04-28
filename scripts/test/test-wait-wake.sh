#!/usr/bin/env bash
set -e

this_dir="$( cd "$( dirname "$0" )" && pwd )"
src_dir="$(realpath "${this_dir}/../..")"

actual="$(sox "${src_dir}/etc/test/hey_mycroft.wav" -r 16000 -e signed-integer -c 1 -t raw - | voice2json "$@" wait-wake --exit-count 1 --audio-source - --exit-timeout 1 | jq -r .keyword)"

if [[ -z "${actual}" ]]; then
    echo "Got empty result"
    exit 1
fi
