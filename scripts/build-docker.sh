#!/usr/bin/env bash
set -e

# Directory of *this* script
this_dir="$( cd "$( dirname "$0" )" && pwd )"
src_dir="$(realpath "${this_dir}/..")"

version="$(cat "${src_dir}/VERSION")"

# -----------------------------------------------------------------------------

: "${PLATFORMS=linux/amd64,linux/arm/v7,linux/arm64}"
: "${DOCKER_REGISTRY=docker.io}"

DOCKERFILE="${src_dir}/Dockerfile"

docker buildx build \
        "${src_dir}" \
        -f "${DOCKERFILE}" \
        "--platform=${PLATFORMS}" \
        --tag "${DOCKER_REGISTRY}/synesthesiam/voice2json:latest" \
        --push \
        "$@"
