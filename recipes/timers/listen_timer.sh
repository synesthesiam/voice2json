#!/usr/bin/env bash
this_dir="$( cd "$( dirname "$0" )" && pwd )"

# Train profile first
voice2json train-profile

# Use a temporary WAV file for recorded command.
# Clean up when this script exits.
temp_wav="$(mktemp)"
function finish {
    rm -rf "${temp_wav}"
    exit 0
}

trap finish SIGTERM SIGINT

# ----------

while true;
do
    # Wait for an MQTT message
    echo 'Waiting for MQTT message on timer/wake-up'
    mosquitto_sub -t 'timer/wake-up' -C 1

    # Play a sound to tell the user we're recording
    aplay "${this_dir}/beep_hi.wav"

    # Record voice command until silence
    echo 'Recording voice command...'
    voice2json record-command > "${temp_wav}"

    # Play a sound to tell the user we're done recording
    aplay "${this_dir}/beep_lo.wav" &

    # 1. Transcribe the WAV file.
    # 2. Recognize the intent from the transcription.
    # 3. Wait until the timer is up
    # 4. Play an alarm sound
    echo 'Recognizing intent...'
    voice2json transcribe-wav "${temp_wav}" | \
        tee >(jq --raw-output '.text' > /dev/stderr) | \
        voice2json recognize-intent | \
        while read -r intent_json;
        do
            echo "${intent_json}"

            # Verify intent is SetTimer
            intent_name="$(echo "${intent_json}" | jq -r .intent.name)"
            if [[ "${intent_name}" == 'SetTimer' ]]; then
                # Wait for timer
                echo "${intent_json}" | python3 "${this_dir}/do_timer.py"

                # Send an MQTT response
                mosquitto_pub -t 'timer/alarm' -m "${intent_json}"

                # Play an alarm sound
                aplay "${this_dir}/alarm.wav"
            fi
        done
done
