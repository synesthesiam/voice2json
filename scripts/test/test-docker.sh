#!/usr/bin/env bash
set -e

# Directory of *this* script
this_dir="$( cd "$( dirname "$0" )" && pwd )"
src_dir="$(realpath "${this_dir}/../..")"

version="$(cat "${src_dir}/VERSION")"

# -----------------------------------------------------------------------------

if [[ -z "$1" ]]; then
    targets=('amd64' 'armv7' 'arm64')
else
    targets=("$@")
fi

# -----------------------------------------------------------------------------

# Create a temporary directory for testing
temp_dir="$(mktemp -d)"

function cleanup {
    rm -rf "${temp_dir}"
}

trap cleanup EXIT

# -----------------------------------------------------------------------------

declare -A target_to_arch
target_to_arch=(['amd64']='amd64' ['armv6']='arm' ['armv7']='arm' ['arm64']='arm64')

declare -A target_to_variant
target_to_variant=(['amd64']='' ['armv6']='v6' ['armv7']='v7' ['arm64']='')

echo "${targets[@]}"

for target in "${targets[@]}"; do
    target_dir="${temp_dir}/${target}"
    rm -rf "${target_dir}"
    mkdir -p "${target_dir}"

    target_platform='linux'
    target_arch="${target_to_arch[${target}]}"
    target_variant="${target_to_variant[${target}]}"

    if [[ -z "${target_variant}" ]]; then
        platform="${target_platform}/${target_arch}"
    else
        platform="${target_platform}/${target_arch}/${target_variant}"
    fi

    echo "target=${target}, arch=${target_arch}, variant=${target_variant}"

    # Create voice2json script for testing
    echo '#!/usr/bin/env bash
docker run \
        --platform "${voice2json_platform}" \
        -v "${HOME}:${HOME}" \
        -e "HOME=${HOME}" \
        --user "$(id -u):$(id -g)" \
        "${DOCKER_REGISTRY}/synesthesiam/voice2json:${voice2json_version}" "$@"
' > "${target_dir}/voice2json"
    chmod +x "${target_dir}/voice2json"

    export voice2json_platform="${platform}"
    export voice2json_version="${version}"

    # Execute test scripts
    PATH="${target_dir}:${PATH}" \
    TMPDIR="${HOME}/.cache" \
        "${src_dir}/scripts/test/test-all.sh" "${HOME}/opt/voice2json-profiles/english" en-us_kaldi-zamia
done
