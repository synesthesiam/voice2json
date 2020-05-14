#!/usr/bin/env bash
set -e

if [[ -z "$1" ]]; then
    echo "Usage: build-debian dist/"
    exit 1
fi

dist_dir="$(realpath "$1")"
mkdir -p "${dist_dir}"
shift

# Directory of *this* script
this_dir="$( cd "$( dirname "$0" )" && pwd )"
src_dir="$(realpath "${this_dir}/..")"

version="$(cat "${src_dir}/VERSION")"

# -----------------------------------------------------------------------------

: "${PLATFORMS=linux/amd64,linux/arm/v7,linux/arm64,linux/arm/v6}"

# ------------------------------------------------------------------------------

echo "Building..."
docker buildx build \
       "${src_dir}" \
       -f "${src_dir}/Dockerfile.debian" \
       "--platform=${PLATFORMS}" \
       --output "type=local,dest=${dist_dir}"
