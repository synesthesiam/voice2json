#!/usr/bin/env bash
set -e

# Directory of *this* script
this_dir="$( cd "$( dirname "$0" )" && pwd )"
src_dir="$(realpath "${this_dir}/..")"

version="$(cat "${src_dir}/VERSION")"

# -----------------------------------------------------------------------------

if [[ -z "$1" ]]; then
    platforms='linux/amd64,linux/arm/v7,linux/arm/v6,linux/arm64'
    use_buildx='yes'
else
    targets=("$@")
    use_buildx='no'
fi

# -----------------------------------------------------------------------------

if [[ "${use_buildx}" = 'yes' ]]; then
    echo TODO
else
    declare -A target_to_arch
    target_to_arch=(['amd64']='amd64' ['armv6']='arm' ['armv7']='arm' ['arm64']='arm64')

    declare -A target_to_variant
    target_to_variant=(['amd64']='' ['armv6']='v6' ['armv7']='v7' ['arm64']='')

    echo "${targets[@]}"

    for target in "${targets[@]}"; do
        target_platform='linux'
        target_arch="${target_to_arch[${target}]}"
        target_variant="${target_to_variant[${target}]}"

        echo "target=${target}, arch=${target_arch}, variant=${target_variant}"
        docker build \
               --build-arg "TARGETPLATFORM=${target_platform}" \
               --build-arg "TARGETARCH=${target_arch}" \
               --build-arg "TARGETVARIANT=${target_variant}" \
               "${src_dir}" \
               -t "${target}/voice2json:${version}"
    done
fi
