#!/usr/bin/env bash
set -e

if [[ -z "$1" ]]; then
    echo "Usage: build-debian dist/ [target] [target]"
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

if [[ -z "$1" ]]; then
    targets=('amd64' 'armv6' 'armv7' 'arm64')
else
    targets=("$@")
fi

declare -A target_to_debian
target_to_debian=(['amd64']='amd64' ['armv6']='armel' ['armv7']='armhf' ['arm64']='aarch64')

declare -A target_to_arch
target_to_arch=(['amd64']='amd64' ['armv6']='arm' ['armv7']='arm' ['arm64']='arm64')

declare -A target_to_variant
target_to_variant=(['amd64']='' ['armv6']='v6' ['armv7']='v7' ['arm64']='')

echo "${targets[@]}"

for target in "${targets[@]}"; do
    debian_arch="${target_to_debian[${target}]}"
    target_arch="${target_to_arch[${target}]}"
    target_variant="${target_to_variant[${target}]}"

    echo "target=${target}, debian=${debian_arch}, arch=${target_arch}, variant=${target_variant}"

    if [[ -z "${debian_arch}" ]]; then
        echo "Invalid debian arch"
        exit 1
    fi

    if [[ -z "${target_arch}" ]]; then
        echo "Invalid target arch"
        exit 1
    fi

    echo "Building..."
    docker build \
           --build-arg TARGETPLATFORM=linux \
           --build-arg "TARGETARCH=${target_arch}" \
           --build-arg "TARGETVARIANT=${target_variant}" \
           --build-arg "VERSION=${version}" \
           --build-arg "DEBIANARCH=${debian_arch}" \
           "${src_dir}" \
           -f Dockerfile.debian \
           -t "${target}/voice2json-debian:${version}"

    echo "Packaging..."
    package_name="voice2json_${version}_${debian_arch}"
    docker run --rm -i --entrypoint /bin/cat \
           "${target}/voice2json-debian:${version}" \
           "/build/${package_name}.deb" > "${dist_dir}/${package_name}.deb"

    echo "Wrote ${dist_dir}/${package_name}.deb"
done
