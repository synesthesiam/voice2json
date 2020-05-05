#!/usr/bin/env bash

# -----------------------------------------------------------------------------
# Helper script to download profile files from voice2json's print-downloads
# command. Requires curl.
#
# Use --dry-run to see commands that would be executed.
# -----------------------------------------------------------------------------

dry_run=''

if [[ "$1" = '--help' ]]; then
    # Print help message
    echo 'Usage: download-files.sh [--dry-run]'
    exit 0
fi

if [[ "$1" = '--dry-run' ]]; then
    dry_run='yes'
fi

# -----------------------------------------------------------------------------

# Read output of `voice2json print-downloads --only-missing`
while read -r json; do
    # Source URL
    url="$(echo "${json}" | jq --raw-output .url)"

    # Destination directory and file path
    profile_dir="$(echo "${json}" | jq --raw-output '.["profile-directory"]')"
    dest_file="$(echo "${json}" | jq --raw-output .file)"
    dest_file="${profile_dir}/${dest_file}"

    # Directory of destination file
    dest_dir="$(dirname "${dest_file}")"

    echo "${url} => ${dest_file}"

    if [[ -z "${dry_run}" ]]; then
        # Create destination directory and download file
        mkdir -p "${dest_dir}"
        curl -sSfL -o "${dest_file}" "${url}"
    else
        # Dry run
        echo mkdir -p "${dest_dir}"
        echo curl -sSfL -o "${dest_file}" "${url}"
    fi
done
