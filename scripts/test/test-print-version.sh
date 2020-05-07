#!/usr/bin/env bash
set -e

this_dir="$( cd "$( dirname "$0" )" && pwd )"
src_dir="$(realpath "${this_dir}/../..")"

expected="$(cat "${src_dir}/VERSION")"
actual="$(voice2json "$@" print-version)"

if [[ "${actual}" != "${expected}" ]]; then
    echo "Expected '${expected}' got '${actual}'"
    exit 1
fi
