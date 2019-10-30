# voice2json Recipes

Below are small demonstrations of how to use `voice2json` for a specific problem or as part of a larger system.

* [Picard's Tea](#picards-tea)
* [MQTT Transcription Service](#create-an-mqtt-transcription-service)
* [Text to Speech Server](#run-a-text-to-speech-server)
* [Launch Programs](#launch-a-program-via-voice)
* [Set Timers](#set-and-run-timers)
* [Parallel Recognition](#parallel-wav-recognition)
* [Rasa NLU Bot](#train-a-rasa-nlu-bot)
* [Microphone Over Network](#stream-microphone-audio-over-a-network)
* [Use DeepSpeech](#use-mozillas-deepspeech)
* [Fluent AI Dataset](#fluent-ai-dataset)

---

## Picard's Tea

This is a simple, fun example to recognize orders for tea from folks like [Jean-Luc Picard](https://memory-alpha.fandom.com/wiki/Earl_Grey_tea).
It accepts the infamous "tea, earl grey, hot" order as well as a few others, such as "tea, green, lukewarm".

```
[MakeTea]
type = (earl grey) | green | black
temperature = hot | lukewarm | cold
tea (<type>){type} (<temperature>){temperature}
```

Saying "tea, earl grey, hot" will output something like:

```json
{
  "text": "tea earl grey hot",
  "intent": {
    "name": "MakeTea",
  },
  "slots": {
    "type": "earl grey",
    "temperature": "hot"
  }
}
```

The strength of `voice2json` is its ability to be quickly customized for how **you** expect a command to be given.

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

## Run a Text to Speech Server

If your profile has a [MaryTTS](http://mary.dfki.de/) voice available (see `text-to-speech.marytts.voice` in your [profile](profiles.md)), you can easily run a local MaryTTS web server at [http://localhost:59125](http://localhost:59125) with the [speak-sentence](commands.md#speak-sentence) command:

```bash
$ voice2json --debug speak-sentence
```

It'll wait forever for input from stdin, so you can interact with the MaryTTS server via `curl`:

```bash
$ curl 'localhost:59125/process?INPUT_TEXT=hello%20world.&INPUT_TYPE=TEXT&AUDIO=WAVE&OUTPUT_TYPE=AUDIO&LOCALE=en-US&VOICE=cmu-slt-hsmm' | aplay
```

Note the period (`.`) at the end of the sentence. MaryTTS seems **very** sensitive to punctutation, so don't forget it!

If you want more voices, copy the JAR(s) and other files into the `marytts` directory in your profile directory (`${profile_dir}/marytts` is set as `MARY_BASE`). See the `text-to-speech.marytts.server-command` property in your [profile](profiles.md) for exactly how `voice2json` starts MaryTTS.

---

## Launch a Program via Voice

* [Source Code](https://github.com/synesthesiam/voice2json/tree/master/recipes/launch_program)

Let's use `voice2json` to launch programs using voice commands. This will follow a typical voice assistant flow, meaning we will:

1. Wait for a wake word to be spoken
2. Record the voice command
3. Recognize and handle the intent

The [listen_and_launch.sh](https://github.com/synesthesiam/voice2json/blob/master/recipes/launch_program/listen_and_launch.sh) script realizes these steps in a bash `while` loop using the [wait-wake](commands.md#wait-wake) and [record-command](commands.md#record-command) `voice2json` commands to do steps 1 and 2. For step 3, [transcribe-wav](commands.md#transcribe-wav) and [recognize-intent](commands.md#recognize-intent) are used.

Our `sentences.ini` file is very simple:

```
[LaunchProgram]
(start | run | launch) ($program){program}
```

We keep the list of supported programs in a `slots/program` file:

```
firefox
web: browser:firefox
file: browser:nemo
text: editor:xed
gimp
mail:thunderbird
```

Note the use of [substitutions](sentences.md#wordtag-substitutions) to map spoken program names (e.g., "web browser", "mail") to actual binary names (`firefox`, `thunderbird`). A few words were added to `custom_words.txt` using [pronounce-word](commands.md#pronounce-word) to guess their pronunciations.

After following the [installation instructions](https://github.com/synesthesiam/voice2json/tree/master/recipes/launch_program), we can execute the [listen_and_launch.sh](https://github.com/synesthesiam/voice2json/blob/master/recipes/launch_program/listen_and_launch.sh) script. After saying the wake word ("porcupine" by default), you should be able to say "run firefox" and have it launch a Firefox window.

---

## Set and Run Timers

* [Source Code](https://github.com/synesthesiam/voice2json/tree/master/recipes/timers)

A common task for voice assistants is to set timers. Here, we demonstrate a "simple" timer that supports a single timer that's less than 10 hours in one second increments:

```
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

There are over 8 million possible sentences here, such as "set a timer for two hours and ten and a half minutes". This template makes heavy use of [substitutions](sentences.md#wordtag-substitutions) to relieve the burden on the intent handler. All number words (e.g., "one") are mapped to digits (e.g. "1"). For multi-word numbers, like "thirty five", the mapped string will be "30 5". Because `hours`, `minutes`, and `seconds` are kept in separate slots, these strings can simply be split by whitespace, converted to integers, and summed to get the intended value:

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

After following the [installation instructions](https://github.com/synesthesiam/voice2json/tree/master/recipes/timers), execute the [listen_timer.sh](https://github.com/synesthesiam/voice2json/blob/master/recipes/timers/listen_timer.sh) script. It will wait for a "wake up" MQTT message on the `timer/wake-up` topic. If you'd like to use a wake word instead, see the [launch program example](#launch-a-program-via-voice).

When the wake up message is received, you can say something like "set a timer for five seconds". After an acknowledgment beep, the example will wait the appropriate amount of time and then play an alarm sound (three short beeps). A response MQTT message is also published on the `timer/alarm` topic after the timer has finished, allowing a [Node-RED](https://nodered.org) or other IoT software to respond.

---

## Parallel WAV Recognition

Want to recognize intents in a large number of WAV files as fast as possible? You can use the [GNU Parallel](http://www.gnu.org/s/parallel) utility with `voice2json` to put those extra CPU cores to good use!

```bash
$ find /path/to/wav/files/ -name '*.wav' | \
      tee wav-file-names.txt | \
      parallel -k --pipe -n 10 \
         'voice2json transcribe-wav --stdin-files | voice2json recognize-intent'
```

This will run up to 10 copies of `voice2json` in parallel and output a line of JSON per WAV file *in the same order as they were printed by the find command*. For convenience, the file names are saved to a text file named `wav-file-names.txt`.

If you want to check `voice2json`'s performance on a directory of WAV files and transcriptions, see the [test-examples](commands.md#test-examples) command.

---

## Train a Rasa NLU Bot

* [Source Code](https://github.com/synesthesiam/voice2json/tree/master/recipes/train_rasa)

Intent recognition in `voice2json` is not very flexible. Similar words and phrasings cannot be substituted, and there is little room for error.
If your voice command system will also be accessible via chat, you may want to use a proper [natural language understanding system](https://rasa.com/docs/rasa/nlu/about/).

`voice2json` can [generate training examples](commands.md#generate-examples) for machine learning systems like Rasa NLU. In this recipe, we use the default English sentences:

```
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

For ease of installation, create a `rasa` script that calls out to the [official Rasa Docker image](https://rasa.com/docs/rasa/user-guide/running-rasa-with-docker/):

```bash
#!/usr/bin/env bash
docker run -it -v "$(pwd):/app" -p 5005:5005 rasa/rasa:latest-spacy-en "$@"
```

Note that the current directory is mounted and port 5005 is exposed. Next, we create a `config.yml`:

```yaml
language: "en"

pipeline: "pretrained_embeddings_spacy"
```

We use the [generate-examples](commands.md#generate-examples) command to randomly generate 5,000 intents with slots.
Beware that no attempt is made in this toy example to [balance classes](https://rasa.com/docs/rasa/nlu/choosing-a-pipeline/#id11).

```bash
$ mkdir -p data && \
      voice2json generate-examples -n 5000 | \
      python3 examples_to_rasa.py > data/training-data.md
```

Next, we train a model. This can take a few minutes, depending on your hardware:

```bash
$ mkdir -p models && \
      ./rasa train nlu
```

Once your model is trained, you can run a test shell:

```bash
$ mkdir -p models && \
      ./rasa shell nlu
```

Try typing in sentences and checking the output.

### Intent HTTP Server

If you want to recognize intents remotely, you should use Rasa's [HTTP Server](https://rasa.com/docs/rasa/user-guide/running-the-server/).

```bash
$ ./rasa run -m models --enable-api
```


With that running, you can `POST` some JSON to port 5005 in a different terminal and get a JSON response:

```bash
$ curl -X POST -d '{ "text": "turn on the living room lamp" }' localhost:5005/model/parse
```

You can easily combine this with `voice2json` to do transcription + intent recognition:

```bash
$ voice2json transcribe-wav \
     ../../etc/test/turn_on_living_room_lamp.wav | \
  curl -X POST -d @- localhost:5005/model/parse
```

Outputs:

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

Try something that `voice2json` would choke on, like "please turn off the light in the living room":

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

Happy recognizing!

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

---

## Use Mozilla's DeepSpeech

* [Source Code](https://github.com/synesthesiam/voice2json/tree/master/recipes/deepspeech)

You can use some of [the artifacts](whitepaper.md#language-model) generated by `voice2json` with [Mozilla's DeepSpeech](https://github.com/mozilla/DeepSpeech). This has only been tested with their [pre-trained English model](https://github.com/mozilla/DeepSpeech#getting-the-pretrained-model).

After following the [installation instructions](https://github.com/synesthesiam/voice2json/tree/master/recipes/deepspeech), you can run the `deep_transcribe.py` Python script to use DeepSpeech for transcriptions instead of `voice2json`. Unlike the general (open) language model, it should be better at recognizing commands from your profile.

```bash
$ ./deep_transcribe.py ../../etc/test/turn_on_living_room_lamp.wav
```

outputs (for me):

```json
{
  "text": "turn on the living room lamp",
  "transcribe_seconds": 2.377969980239868,
  "wav_name": "turn_on_living_room_lamp.wav",
  "wav_seconds": 2.402375
}
```

With a supported GPU, you should be able to get better transcription times.

---

## Fluent AI Dataset

The good folks at [Fluent AI](http://www.fluent.ai) have a [speech command dataset](http://www.fluent.ai/research/fluent-speech-commands/) available for community use. The training set includes over 23,000 spoken examples, and the test set has about 3,800 commands. Each command has at most three attributes: action, object, and location; for example: "turn on (*action*) the lights (*object*) in the kitchen (*location*)". The object and location may be omitted in certain commands, but the action (intent) is always present.

Using ~100 lines in [sentences.ini](https://github.com/synesthesiam/voice2json/blob/master/recipes/fluent_dataset/sentences.ini) (excluding comments), I'm able to get **98.7% accuracy** on the test set, which is as accurate as the end-to-end system trained in [Fluent.ai's published paper](https://arxiv.org/pdf/1904.03670.pdf)! While the sentences `voice2json` was trained with had to be hand-tuned to fit the test set, it also did not require any audio training data.

If you'd like to reproduce my results, follow the [installation instructions](https://github.com/synesthesiam/voice2json/tree/master/recipes/fluent_dataset) and double-check my work :)
