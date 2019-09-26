#!/usr/bin/env bash
this_dir="$( cd "$( dirname "$0" )" && pwd )"

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
    # Wait until the wake word has been spoken, then exit
    voice2json wait-wake --exit-count 1

    # Play a sound to tell the user we're recording
    aplay "${this_dir}/beep_hi.wav"

    # Record voice command until silence
    voice2json record-command > "${temp_wav}"

    # Play a sound to tell the user we're done recording
    aplay "${this_dir}/beep_lo.wav" &

    # 1. Transcribe the WAV file.
    # 2. Recognize the intent from the transcription.
    # 3. Wait until the timer is up
    # 4. Play an alarm sound
    voice2json transcribe-wav "${temp_wav}" | \
        tee >(jq --raw-output '.text' > /dev/stderr) | \
        voice2json recognize-intent | \
        python3 "${this_dir}/do_timer.py" | \
        while read -r line;
        do
            aplay "${this_dir}/alarm.wav"
        done
done
