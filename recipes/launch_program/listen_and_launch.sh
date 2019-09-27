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
    # Wait until the wake word has been spoken, then exit
    echo 'Waiting for wake word...'
    voice2json wait-wake --exit-count 1

    # Play a sound to tell the user we're recording
    aplay "${this_dir}/beep_hi.wav"

    # Record voice command until silence
    echo 'Recording voice command...'
    voice2json record-command > "${temp_wav}"

    # Play a sound to tell the user we're done recording
    aplay "${this_dir}/beep_lo.wav" &

    # 1. Transcribe the WAV file.
    # 2. Recognize the intent from the transcription.
    # 3. Extract the name of the program to launch
    echo 'Recognizing intent...'
    voice2json transcribe-wav "${temp_wav}" | \
        voice2json recognize-intent | \
        while read -r intent_json;
        do
            echo "${intent_json}"

            # Verify intent is LaunchProgram
            intent_name="$(echo "${intent_json}" | jq -r .intent.name)"
            if [[ "${intent_name}" == 'LaunchProgram' ]]; then

                # Extract "program" slot value
                program="$(echo "${intent_json}" | jq -r .slots.program)"
                if [[ ! -z "${program}" ]]; then
                    # Run the program.
                    # For simplicity, we assume its the name of a binary in /usr/bin.
                    program_exe="/usr/bin/${program}"
                    echo "Running ${program_exe}"

                    # Detach the process from this terminal, so it will keep running.
                    nohup "${program_exe}" &
                else
                    echo 'No program was found in intent'
                fi
            else
                echo "Expected LaunchProgram intent, got ${intent_name}"
            fi
        done
done
