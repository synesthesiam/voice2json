#!/usr/bin/env bash
set -e

# Directory of *this* script
this_dir="$( cd "$( dirname "$0" )" && pwd )"
src_dir="$(realpath "${this_dir}/../..")"

version="$(cat "${src_dir}/VERSION")"

# -----------------------------------------------------------------------------

profiles=()

if [[ -z "$1" ]]; then
    platforms=('linux/amd64' 'linux/arm/v7' 'linux/arm64')
else
    on_profiles=''
    platforms=()

    while [[ ! -z "$1" ]]; do
        if [[ "$1" = '--' ]]; then
            on_profiles='yes'
        elif [[ -z "${on_profiles}" ]]; then
            platforms+=("$1")
        else
            profiles+=("$1")
        fi

        shift
    done
fi

# -----------------------------------------------------------------------------

docker buildx build "${src_dir}" \
       -f "${src_dir}/Dockerfile.test.debian" \
       --platform "${platforms[@]}" \
       --tag "${DOCKER_REGISTRY}/synesthesiam/voice2json-debian-test" \
       --push

# -----------------------------------------------------------------------------

# Create a temporary directory for testing
temp_dir="$(mktemp -d)"

function cleanup {
    rm -rf "${temp_dir}"
}

trap cleanup EXIT

# -----------------------------------------------------------------------------

declare -A platform_to_target
platform_to_target=(['linux/amd64']='amd64' ['linux/arm/v6']='armv6' ['linux/arm/v7']='armv7' ['linux/arm64']='arm64')

for platform in "${platforms[@]}"; do
    echo "${platform}"
    target="${platform_to_target["${platform}"]}"
    if [[ -z "${target}" ]]; then
        echo "ERROR: ${platform}"
        exit 1
    fi

    docker pull  \
           --platform "${platform}" \
           "${DOCKER_REGISTRY}/synesthesiam/voice2json-debian-test"

    target_dir="${temp_dir}/${target}"
    rm -rf "${target_dir}"
    mkdir -p "${target_dir}"

    # Create voice2json script for testing
    echo '#!/usr/bin/env bash
docker run -i \
        --platform "${voice2json_platform}" \
        -v "${HOME}:${HOME}" \
        -e "HOME=${HOME}" \
        --user "$(id -u):$(id -g)" \
        "${DOCKER_REGISTRY}/synesthesiam/voice2json-debian-test" "$@"
' > "${target_dir}/voice2json"
    chmod +x "${target_dir}/voice2json"

    export voice2json_platform="${platform}"
    export voice2json_version="${version}"

    # Execute test scripts
    PATH="${target_dir}:${PATH}" \
    TMPDIR="${HOME}/.cache" \
        "${src_dir}/scripts/test/test-all.sh" "${HOME}/opt/voice2json-profiles/english" "${profiles[@]}"
done
