#!/usr/bin/env bash
this_dir="$( cd "$( dirname "$0" )" && pwd )"

# -----------------------------------------------------------------------------
# Command-line Arguments
# -----------------------------------------------------------------------------

. "${this_dir}/etc/shflags"

DEFINE_string 'profile' "${voice2json_profile}" 'Path to voice2json profile'
DEFINE_string 'cache' '' 'Path to download directory'
DEFINE_string 'http-host' '127.0.0.1' 'HTTP server host'
DEFINE_integer 'http-port' 5000 'MQTT HTTP server port'
DEFINE_string 'mqtt-host' '127.0.0.1' 'MQTT server host'
DEFINE_integer 'mqtt-port' 1883 'MQTT server port'
DEFINE_boolean 'venv' true 'Use virtual environment if available'
DEFINE_boolean 'mosquitto' false 'Run mosquitto daemon'

FLAGS "$@" || exit $?
eval set -- "${FLAGS_ARGV}"

# -----------------------------------------------------------------------------
# Default Settings
# -----------------------------------------------------------------------------

set -e

args=('--debug')

profile="${FLAGS_profile}"

if [[ -z "${profile}" ]]; then
    # Try XDG_CONFIG_HOME
    config_home="${XDG_CONFIG_HOME}"
    if [[ -z "${config_home}" ]]; then
        config_home="${HOME}/.config"
    fi

    # $HOME/.config/voice2json
    profile="${config_home}/voice2json"
fi

download_dir="${FLAGS_cache}"

export http_host="${FLAGS_http_host}"
export http_port="${FLAGS_http_port}"
export mqtt_host="${FLAGS_mqtt_host}"
export mqtt_port="${FLAGS_mqtt_port}"

if [[ "${FLAGS_venv}" -eq "${FLAGS_FALSE}" ]]; then
    no_venv="true"
fi

if [[ "${FLAGS_mosquitto}" -eq "${FLAGS_TRUE}" ]]; then
    mosquitto -d
fi

# -----------------------------------------------------------------------------

# Load virtual environment
if [[ -z "${voice2json_dir}" ]]; then
    export voice2json_dir="$(realpath "${this_dir}/..")"
fi

venv="${this_dir}/.venv"

if [[ -d "${venv}" && -z "${no_venv}" ]]; then
    echo "Using virtual environment at ${venv}"
    source "${venv}/bin/activate"
fi

export PYTHONPATH="${voice2json_dir}:${PYTHONPATH}"

# -----------------------------------------------------------------------------

if [[ -e "${profile}" ]]; then
    # Do full training
    if [[ -f "${profile}/clean.sh" ]]; then
        bash "${profile}/clean.sh"
    fi

    voice2json --profile "${profile}" train-profile

    # Run web server and MQTT services
    export voice2json_profile="${profile}"

    current_dir="$(pwd)"
    cd "${this_dir}" && \
        supervisord \
            --config "${this_dir}/supervisord.conf" \
            --logfile "${current_dir}/supervisord.log" \
            --pidfile "${current_dir}/supervisord.pid"
else
    if [[ -z "${download_dir}" ]]; then
        cache_home="${XDG_CACHE_HOME}"
        if [[ -z "${cache_home}" ]]; then
            cache_home="${HOME}/.cache"
        fi

        download_dir="${cache_home}/voice2json"
    fi

    # Run profile downloader
    cd "${voice2json_dir}" && \
        python3 -m mqtt.app_noprofile \
                --profile "${profile}" \
                --cache "${download_dir}" \
                --http-host "${http_host}" \
                --http-port "${http_port}" \
                "${args[@]}"
fi
