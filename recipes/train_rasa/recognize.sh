#!/usr/bin/env bash
set -e

if [[ -z "$(which docker)" ]]; then
    echo "You will need Docker to run this example"
    exit 1
fi

echo "Loading. Please wait..."
bash rasa shell nlu
