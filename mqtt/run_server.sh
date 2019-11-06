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
DEFINE_boolean 'debug' false 'Print DEBUG message to console'

FLAGS "$@" || exit $?
eval set -- "${FLAGS_ARGV}"

# -----------------------------------------------------------------------------
# Default Settings
# -----------------------------------------------------------------------------

set -e

args=()

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

http_host="${FLAGS_http_host}"
if [[ ! -z "${http_host}" ]]; then
    args+=('--http-host' "${http_host}")
fi

http_port="${FLAGS_http_port}"
if [[ ! -z "${http_port}" ]]; then
    args+=('--http-port' "${http_port}")
fi

mqtt_host="${FLAGS_mqtt_host}"
mqtt_port="${FLAGS_mqtt_port}"

if [[ "${FLAGS_debug}" -eq "${FLAGS_TRUE}" ]]; then
    args+=('--debug')
fi

# -----------------------------------------------------------------------------

# Load virtual environment
if [[ -z "${voice2json_dir}" ]]; then
    export voice2json_dir="$(realpath "${this_dir}/..")"
fi

venv="${this_dir}/.venv"

if [[ -d "${venv}" ]]; then
    echo "Using virtual environment at ${venv}"
    source "${venv}/bin/activate"
fi

export PYTHONPATH="${voice2json_dir}:${PYTHONPATH}"

# -----------------------------------------------------------------------------

if [[ -e "${profile}" ]]; then
    if [[ ! -z "${mqtt_host}" ]]; then
        args+=('--mqtt-host' "${mqtt_host}")
    fi

    if [[ ! -z "${mqtt_port}" ]]; then
        args+=('--mqtt-port' "${mqtt_port}")
    fi

    # Do training
    voice2json --profile "${profile}" train-profile

    # Run web server and MQTT services
    export server_args="--profile \"${profile}\" ${args[@]}"
    export service_args="--profile \"${profile}\""
    supervisord --config "${this_dir}/supervisord.conf"
else
    if [[ -z "${download_dir}" ]]; then
        cache_home="${XDG_CACHE_HOME}"
        if [[ -z "${cache_home}" ]]; then
            cache_home="${HOME}/.cache"
        fi

        download_dir="${cache_home}/voice2json"
    fi

    # Run profile downloader
    python3 -m mqtt.app_noprofile \
            --profile "${profile}" \
            --cache "${download_dir}" \
            "${args[@]}"
fi
