![voice2json logo](docs/img/voice2json.svg)

`voice2json` is a collection of [command-line tools](https://voice2json.org/commands.html) for <strong>offline speech/intent recognition</strong> on Linux. It is free, open source, and [supports 15 languages](https://voice2json.org/index.html#supported-languages). 

* [Getting Started](https://voice2json.org/#getting-started)
* [Commands](https://voice2json.org/comands.html)
* [Recipes](https://voice2json.org/recipes.html)
* [About](https://voice2json.org/about.html)

From the command-line:

```bash
$ voice2json transcribe-wav \
      < turn-on-the-light.wav | \
      voice2json recognize-intent | \
      jq .
```

produces a [JSON event](https://voice2json.org/formats.html) like:

```json
{
    "text": "turn on the light",
    "intent": {
        "name": "LightState"
    },
    "slots": {
        "state": "on"
    }
}
```

when trained with this [template](https://voice2json.org/sentences.html):

```
[LightState]
states = (on | off)
turn (<states>){state} [the] light
```

`voice2json` is <strong>optimized for</strong>:

* Sets of voice commands that are described well [by a grammar](https://voice2json.org/sentences.html)
* Commands with [uncommon words or pronunciations](https://voice2json.org/commands.html#pronounce-word)
* Commands or intents that [can vary at runtime](#unique-features)

It can be used to:

* Add voice commands to [existing applications or Unix-style workflows](https://voice2json.org/recipes.html#create-an-mqtt-transcription-service)
* Provide basic [voice assistant functionality](https://voice2json.org/recipes.html#set-and-run-timers) completely offline on modest hardware
* Bootstrap more [sophisticated speech/intent recognition systems](https://voice2json.org/recipes.html#train-a-rasa-nlu-bot)

---

## Unique Features

`voice2json` is more than just a wrapper around [pocketsphinx](https://github.com/cmusphinx/pocketsphinx) and [Kaldi](https://kaldi-asr.org)!

* Training produces **both** a speech and intent recognizer. By describing your voice commands with `voice2json`'s [templating language](https://voice2json.org/sentences.html), you get [more than just transcriptions](https://voice2json.org/formats.html#intents) for free.
* Re-training is **fast enough** to be done at runtime (usually < 5s), even up to [millions of possible voice commands](https://voice2json.org/recipes.html#set-and-run-times). This means you can change [referenced slot](https://voice2json.org/sentences.html#slot-references) values or [add/remove intents](https://voice2json.org/commands.html#intent-whitelist) on the fly.
* All of the [available commands](#commands) are designed to work well in Unix pipelines, typically consuming/emitting plaintext or [newline-delimited JSON](http://jsonlines.org). Audio input/output is [file-based](https://voice2json.org/commands.html#audio-sources), so you receive audio from [any source](https://voice2json.org/recipes.html#stream-microphone-audio-over-a-network).

## Commands

* [print-profile](https://voice2json.org/commands.html#print-profile) - Print profile settings
* [train-profile](https://voice2json.org/commands.html#train-profile) - Generate speech/intent artifacts
* [transcribe-wav](https://voice2json.org/commands.html#transcribe-wav) - Transcribe WAV file to text
* [recognize-intent](https://voice2json.org/commands.html#recognize-intent) - Recognize intent from JSON or text
* [wait-wake](https://voice2json.org/commands.html#wait-wake) - Listen to live audio stream for wake word
* [record-command](https://voice2json.org/commands.html#record-command) - Record voice command from live audio stream
* [pronounce-word](https://voice2json.org/commands.html#pronounce-word) - Look up or guess how a word is pronounced
* [generate-examples](https://voice2json.org/commands.html#generate-examples) - Generate random intents
* [record-examples](https://voice2json.org/commands.html#record-examples) - Generate and record speech examples
* [test-examples](https://voice2json.org/commands.html#test-examples) - Test recorded speech examples
* [tune-examples](https://voice2json.org/commands.html#tune-examples) - Tune acoustic model using recorded speech examples
* [show-documentation](https://voice2json.org/commands.html#show-documentation) - Run HTTP server locally with documentation
