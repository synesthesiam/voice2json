#!/usr/bin/env bash
set -e

if [[ -z "$(which docker)" ]]; then
    echo "You will need Docker to run this example"
    exit 1
fi

# Number of examples to generate for training.
# More is better.
num_examples=5000

# Ensure profile has been trained
voice2json train-profile

# Generate training examples
echo "Generating ${num_examples} example(s)..."
mkdir -p data
voice2json generate-examples \
           --number "${num_examples}" | \
    python3 examples_to_rasa.py \
            > data/training-data.md

# Train a Rasa NLU bot
mkdir -p models
bash rasa train nlu \
     --verbose

echo "Done"

