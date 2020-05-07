#!/usr/bin/env bash
set -e

this_dir="$( cd "$( dirname "$0" )" && pwd )"
src_dir="$(realpath "${this_dir}/../..")"

word='raxacoricofallipatorius'
actual="$(voice2json "$@" pronounce-word --quiet --nbest 1 "${word}")"

if [[ ! "${actual}" =~ ^${word} ]]; then
    echo "Expected '${word} ...' got '${actual}'"
    exit 1
fi
