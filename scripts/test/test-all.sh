#!/usr/bin/env bash
set -e

if [[ -z "$1" ]]; then
    echo "Usage: test-all.sh profiles-root [PROFILE] [PROFILE] ..."
    exit 1
fi

this_dir="$( cd "$( dirname "$0" )" && pwd )"
src_dir="$(realpath "${this_dir}/../..")"

# Parse command-line
profiles_root=$(realpath "$1")
shift

do_mixed_tests=''
profiles=()
while [[ ! -z "$1" ]]; do
    if [[ "$1" == '--mixed' ]]; then
        do_mixed_tests='yes'
    else
        profiles+=("$1")
    fi

    shift
done

# -----------------------------------------------------------------------------

# Create a temporary directory for extraction
temp_dir="$(mktemp -d)"

function cleanup {
    rm -rf "${temp_dir}"
}

trap cleanup EXIT

# -----------------------------------------------------------------------------

# Profile names to test
if [[ -z "${profiles[*]}" ]]; then
    # All profiles
    profiles=('en-us_pocketsphinx-cmu' 'en-us_kaldi-zamia' 'en-us_deepspeech-mozilla')
fi

stt_tests=('transcribe-wav' 'open-transcription')
other_tests=('recognize-intent' 'wait-wake')
all_tests=("${stt_tests[@]}" "${other_tests[@]}")

declare -A test_errors

for profile in "${profiles[@]}"; do
    profile_errors=()
    src_profile_dir="${profiles_root}/${profile}"
    dest_profile_dir="${temp_dir}/${profile}"

    # Copy profile files
    echo "${src_profile_dir} => ${dest_profile_dir}"
    rm -rf "${dest_profile_dir}"
    cp -R "${src_profile_dir}" "${dest_profile_dir}"

    # Train
    echo 'Training...'
    voice2json -p "${dest_profile_dir}" --debug train-profile

    # Test
    echo 'Testing...'
    for test_name in "${all_tests[@]}"; do
        echo "${test_name}"
        "${src_dir}/scripts/test/test-${test_name}.sh" --profile "${dest_profile_dir}" --debug || \
            profile_errors+=("${test_name}")
    done

    if [[ ! -z "${do_mixed_tests}" ]]; then
        # Train (mixed)
        echo 'Training (mixed)...'
        voice2json --profile "${dest_profile_dir}" \
                --setting 'training.base-language-model-weight' '0.05' \
                --debug train-profile

        # Test (mixed)
        echo 'Testing (mixed)...'
        for test_name in "${stt_tests[@]}"; do
            echo "${test_name} (mixed)"
            "${src_dir}/scripts/test/test-${test_name}.sh" -p "${dest_profile_dir}" --debug || \
                    profile_errors+=("mixed-${test_name}")
        done
    fi

    # -------------------------------------------------------------------------

    test_errors["${profile}"]="${profile_errors[*]}"

    echo '-------'
    echo ''
done

# -----------------------------------------------------------------------------

echo 'Summary'
echo '-------'
for profile in "${profiles[@]}"; do
    echo "${profile}: ${test_errors["${profile}"]}"
done
