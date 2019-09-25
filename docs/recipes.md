# voice2json Recipes

Below are small demonstrations of how to use `voice2json` for a specific problem or as part of a larger system.

---

## Create an MQTT Transcription Service

`voice2json` is designed to work well in Unix-style workflows. Many of the [commands](commands.md) consume and produce [jsonl](http://jsonlines.org), which makes them interoperable with other line-oriented command-line tools.

The `mosquitto_pub` and `mosquitto_sub` commands included in the `mosquitto-clients` package enable other programs to send and receive messages over the [MQTT protocol](http://mqtt.org). These programs can then easily participate in an IoT system, such as a [Node-RED](https://nodered.org) flow.

For this recipe, start by installing the MQTT client commands:

```bash
$ sudo apt-get install mosquitto-clients
```

We can create a simple transcription service using the [transcribe-wav](commands.md#transcribe-wav) `voice2json` command. This service will receive file paths on a `transcription-request` topic, and send the text transcription out on a `transcription-response` topic.

```bash
$ mosquitto_sub -t 'transcription-request' | \
      voice2json transcribe-wav --stdin-files | \
      while read -r json; \
          do echo "$json" | jq --raw-output .text; \
      done | \
      mosquitto_pub -l -t 'transcription-response'
```

We use the `--stdin-files` argument of [transcribe-wav](commands.md#transcribe-wav) to make it read file paths on standard in and emit a single line of JSON for each transcription. The excellent [jq](https://stedolan.github.io/jq/) tool is used to extract the `text` of the transcription (`--raw-otuput` emits the value without quotes).

With the service running, open a separate terminal and subscribe to the `transcription-response` topic:

```bash
$ mosquitto_sub -t 'transcription-response'
```

Finally, in yet another terminal, send a `transcription-request` with a WAV file path on your system:

```bash
$ mosquitto_pub -t 'transcription-request' -m '/path/to/turn-on-the-light.wav'
```

In the terminal subscribed to `transcription-response` messages, you should see the text transcription printed:

```
turn on the light
```

---

## Launch a Program via Voice

```ini
[LaunchProgram]
(start | run | launch) ($program){program}
```

```
firefox
web: browser:firefox
file: browser:nemo
text: editor:xed
gimp
mail:thunderbird
```

```bash
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
    # 3. Extract the name of the program to launch
    voice2json transcribe-wav "${temp_wav}" | \
        voice2json recognize-text | \
        jq --raw-output '.slots.program' | \
        while read -r program;
        do
            if [[ ! -z "${program}" ]]; then
                # Run the program.
                # For simplicity, we assume its the name of a binary in /usr/bin.
                program_exe="/usr/bin/${program}"
                echo "Running ${program_exe}"

                # Detach the process from this terminal, so it will keep running.
                nohup "${program_exe}" &
            fi
        done
done
```

---

## Set and Run Timers

```ini
[ClearTimer]
clear [the] timer

[SetTimer]
two_to_nine = (two:2 | three:3 | four:4 | five:5 | six:6 | seven:7 | eight:8 | nine:9)
one_to_nine = (one:1 | <two_to_nine>)
teens = (ten:10 | eleven:11 | twelve:12 | thirteen:13 | fourteen:14 | fifteen:15 | sixteen:16 | seventeen:17 | eighteen:18 | nineteen:19)
tens = (twenty:20 | thirty:30 | forty:40 | fifty:50)

one_to_nine = (one:1 | <two_to_nine>)
one_to_fifty_nine = (<one_to_nine> | <teens> | <tens> [<one_to_nine>])
two_to_fifty_nine = (<two_to_nine> | <teens> | <tens> [<one_to_nine>])

hour_half_expr = (<one_to_nine>{hours} and (a half){minutes:30})
hour_expr = (((one:1){hours}) | ((<one_to_nine>){hours}) | <hour_half_expr>) (hour | hours)

minute_half_expr = (<one_to_fifty_nine>{minutes} and (a half){seconds:30})
minute_expr = (((one:1){minutes}) | ((<two_to_fifty_nine>){minutes}) | <minute_half_expr>) (minute | minutes)

second_expr = (((one:1){seconds}) | ((<two_to_fifty_nine>){seconds})) (second | seconds)

time_expr = ((<hour_expr> [[and] <minute_expr>] [[and] <second_expr>]) | (<minute_expr> [[and] <second_expr>]) | <second_expr>)

set [a] timer for <time_expr>
```
Over 8.6 million possible sentences.

```python
#!/usr/bin/env python3
import sys
import json
import time

def parse_time_string(time_str):
    """Parse a string like '30 2' and return the integer 32."""
    return sum(int(n) for n in time_str.split(" "))

for line in sys.stdin:
    intent = json.loads(line)

    # Extract time strings
    hours_str = intent["slots"].get("hours", "0")
    minutes_str = intent["slots"].get("minutes", "0")
    seconds_str = intent["slots"].get("seconds", "0")

    # Parse into integers
    hours = parse_time_string(hours_str)
    minutes = parse_time_string(minutes_str)
    seconds = parse_time_string(seconds_str)

    # Compute total number of seconds to wait
    total_seconds = (hours * 60 * 60) + (minutes * 60) + seconds

    # Wait
    time.sleep(total_seconds)

    # Done
    print("Ready")
```

```bash
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
        voice2json recognize-text | \
        python3 "${this_dir}/do_timer.py" | \
        while read -r line;
        do
            aplay "${this_dir}/alarm.wav"
        done
done
```

---

## Parallel WAV Recognition

Want to recognize intents in a large number of WAV files as fast as possible? You can use the [GNU Parallel](http://www.gnu.org/s/parallel) with `voice2json` to put those extra CPU cores to good use!

```bash
$ find /path/to/wav/files/ -name '*.wav' | \
      tee wav-file-names.txt | \
      parallel -k --pipe -n 10 \
         'voice2json transcribe-wav --stdin-files | voice2json recognize-text'
```

This will run up to 10 copies of `voice2json` in parallel and output a line of JSON per WAV file *in the same order as they were printed by the find command*. For convenience, the file names are saved to a text file named `wav-file-names.txt`.

---

## Train a Rasa NLU Bot

```ini
[GetTime]
what time is it
tell me the time

[GetTemperature]
whats the temperature
how (hot | cold) is it

[GetGarageState]
is the garage door (open | closed)

[ChangeLightState]
light_name = ((living room lamp | garage light) {name}) | <ChangeLightColor.light_name>
light_state = (on | off) {state}

turn <light_state> [the] <light_name>
turn [the] <light_name> <light_state>

[ChangeLightColor]
light_name = (bedroom light) {name}
color = ($colors) {color}

set [the] <light_name> [to] <color>
make [the] <light_name> <color>
```

```python
#!/usr/bin/env python3
import sys
import json
from collections import defaultdict

examples_by_intent = defaultdict(list)

# Gather all examples by intent name
for line in sys.stdin:
    example = json.loads(line)
    intent_name = example["intent"]["name"]
    examples_by_intent[intent_name].append(example)

# Write data in RasaNLU markdown training format
for intent_name, examples in examples_by_intent.items():
    print(f"## intent:{intent_name}")

    for example in examples:
        # Create mapping from start/stop character indexes to example entities
        entities_by_start = {e["raw_start"]: e for e in example["entities"]}
        entities_by_end = {e["raw_end"]: e for e in example["entities"]}

        # Current character index
        char_idx = 0

        # Final list of tokens that will be printed for the example
        tokens_to_print = []

        # Current entity
        entity = None

        # Tokens that belong to the current entity
        entity_tokens = []

        # Process "raw" tokens without substitutions
        for token in example["raw_tokens"]:
            if char_idx in entities_by_start:
                # Start entity
                entity = entities_by_start[char_idx]
                entity_tokens = []

            if entity is None:
                # Use token as-is
                tokens_to_print.append(token)
            else:
                # Accumulate into entity token list
                entity_tokens.append(token)

            # Advance character index in raw text
            char_idx += len(token) + 1  # space

            if (char_idx - 1) in entities_by_end:
                # Finish entity
                entity_str = entity["entity"]
                if entity["value"] != entity["raw_value"]:
                    # Include substitution
                    entity_str += f":{entity['value']}"

                # Create Markdown-style entity
                token_str = "[" + " ".join(entity_tokens) + f"]({entity_str})"
                tokens_to_print.append(token_str)
                entity = None

        # Print example
        print("-", " ".join(tokens_to_print))

    # Blank line between intents
    print("")
```

```yaml
language: "en"

pipeline: "pretrained_embeddings_spacy"
```

```bash
#!/usr/bin/env bash
docker run -it -v "$(pwd):/app" -p 5005:5005 rasa/rasa:latest-spacy-en "$@"
```

```bash
$ mkdir -p data && \
      voice2json generate-examples -n 10000 | \
      python3 examples_to_rasa.py > data/training-data.md
```

```bash
$ mkdir -p models && \
      ./rasa shell nlu
```

```json
{
  "intent": {
    "name": "ChangeLightState",
    "confidence": 0.9986116877633666
  },
  "entities": [
    {
      "start": 5,
      "end": 7,
      "value": "on",
      "entity": "state",
      "confidence": 0.9990940955808785,
      "extractor": "CRFEntityExtractor"
    },
    {
      "start": 12,
      "end": 28,
      "value": "living room lamp",
      "entity": "name",
      "confidence": 0.9989133507400977,
      "extractor": "CRFEntityExtractor"
    }
  ],
  "intent_ranking": [
    {
      "name": "ChangeLightState",
      "confidence": 0.9986116877633666
    },
    {
      "name": "GetGarageState",
      "confidence": 0.0005631913057901469
    },
    {
      "name": "GetTemperature",
      "confidence": 0.0005114253499747637
    },
    {
      "name": "GetTime",
      "confidence": 0.00030957597780200693
    },
    {
      "name": "ChangeLightColor",
      "confidence": 4.119603066327378e-06
    }
  ],
  "text": "turn on the living room lamp"
}
```

```json
{
  "intent": {
    "name": "ChangeLightState",
    "confidence": 0.9504002047698142
  },
  "entities": [
    {
      "start": 12,
      "end": 15,
      "value": "off",
      "entity": "state",
      "confidence": 0.9991999541256443,
      "extractor": "CRFEntityExtractor"
    },
    {
      "start": 33,
      "end": 44,
      "value": "living room",
      "entity": "name",
      "confidence": 0.0,
      "extractor": "CRFEntityExtractor"
    }
  ],
  "intent_ranking": [
    {
      "name": "ChangeLightState",
      "confidence": 0.9504002047698142
    },
    {
      "name": "GetTemperature",
      "confidence": 0.016191147989239697
    },
    {
      "name": "ChangeLightColor",
      "confidence": 0.014916606955255965
    },
    {
      "name": "GetTime",
      "confidence": 0.014345667003407515
    },
    {
      "name": "GetGarageState",
      "confidence": 0.004146373282282381
    }
  ],
  "text": "please turn off the light in the living room"
```

---

## Stream Microphone Audio Over a Network

Using the [gst-launch](https://gstreamer.freedesktop.org/documentation/tools/gst-launch.html) command from [GStreamer](https://gstreamer.freedesktop.org/), you can stream raw audio data from your microphone to another machine over a UDP socket:

```bash
gst-launch-1.0 \
    pulsesrc ! \
    audioconvert ! \
    audioresample ! \
    audio/x-raw, rate=16000, channels=1, format=S16LE ! \
    udpsink host=<Destination IP> port=<Destination Port>
```

where `<Destination IP>` is the IP address of the machine with `voice2json` and `<Destination Port>` is a free port on that machine.

On the destination machine, run:

```bash
$ gst-launch-1.0 \
     udpsrc port=<Destination Port> ! \
     rawaudioparse use-sink-caps=false format=pcm pcm-format=s16le sample-rate=16000 num-channels=1 ! \
     queue ! \
     audioconvert ! \
     audioresample ! \
     filesink location=/dev/stdout | \
  voice2json <Command> --audio-source -
```

where `<Destination IP>` matches the first command and `<Command>` is [wait-wake](commands.md#wait-wake), [record-command](commands.md#record-command), or [record-examples](commands.md#record-examples).

See the GStreamer [multiudpsink plugin](https://gstreamer.freedesktop.org/documentation/udp/multiudpsink.html) for streaming to multiple machines simultaneously (it also has multicast support too).
