![voice2json logo](docs/img/voice2json.svg)

`voice2json` is a collection of [command-line tools](https://voice2json.org/commands.html) for <strong>offline speech/intent recognition</strong> on Linux. It is free, open source ([MIT](https://opensource.org/licenses/MIT)), and [supports 18 human languages](#supported-languages). 

* [Getting Started](https://voice2json.org/#getting-started)
* [Commands](https://voice2json.org/commands.html)
    * [Data Formats](https://voice2json.org/formats.html)
* [Profiles](https://github.com/synesthesiam/voice2json-profiles)
* [Recipes](https://voice2json.org/recipes.html)
* [Node-RED Plugin](https://github.com/johanneskropf/node-red-contrib-voice2json)
* [About](https://voice2json.org/about.html)
    * [Whitepaper](https://voice2json.org/whitepaper.html)

From the command-line:

```bash
$ voice2json -p en transcribe-wav \
      < turn-on-the-light.wav | \
      voice2json -p en recognize-intent | \
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

Supported speech to text systems include:

* CMU's [pocketsphinx](https://github.com/cmusphinx/pocketsphinx)
* Dan Povey's [Kaldi](https://kaldi-asr.org)
* Mozilla's [DeepSpeech](https://github.com/mozilla/DeepSpeech) 0.9
* Kyoto University's [Julius](https://github.com/julius-speech/julius)

---

## Supported Languages

* Catalan (`ca`)
    * [`ca-es_pocketsphinx-cmu`](https://github.com/synesthesiam/ca-es_pocketsphinx-cmu)
* Czech (`cs`)
    * [`cs-cz_kaldi-rhasspy`](https://github.com/rhasspy/cs_kaldi-rhasspy)
* German (`de`)
    * [`de_deepspeech-aashishag`](https://github.com/synesthesiam/de_deepspeech-aashishag)
    * [`de_deepspeech-jaco`](https://github.com/rhasspy/de_deepspeech-jaco)
    * [`de_kaldi-zamia`](https://github.com/synesthesiam/de_kaldi-zamia) (default)
    * [`de_pocketsphinx-cmu`](https://github.com/synesthesiam/de_pocketsphinx-cmu)
* Greek (`el`)
    * [`el-gr_pocketsphinx-cmu`](https://github.com/synesthesiam/el-gr_pocketsphinx-cmu)
* English (`en`)
    * [`en-in_pocketsphinx-cmu`](https://github.com/synesthesiam/en-in_pocketsphinx-cmu)
    * [`en-us_deepspeech-mozilla`](https://github.com/synesthesiam/en-us_deepspeech-mozilla)
    * [`en-us_kaldi-rhasspy`](https://github.com/rhasspy/en-us_kaldi-rhasspy)
    * [`en-us_kaldi-zamia`](https://github.com/synesthesiam/en-us_kaldi-zamia) (default)
    * [`en-us_pocketsphinx-cmu`](https://github.com/synesthesiam/en-us_pocketsphinx-cmu)
* Spanish (`es`)
    * [`es_deepspeech-jaco`](https://github.com/rhasspy/es_deepspeech-jaco)
    * [`es_kaldi-rhasspy`](https://github.com/rhasspy/es_kaldi-rhasspy) (default)
    * [`es-mexican_pocketsphinx-cmu`](https://github.com/synesthesiam/es-mexican_pocketsphinx-cmu)
    * [`es_pocketsphinx-cmu`](https://github.com/synesthesiam/es_pocketsphinx-cmu)
* French (`fr`)
    * [`fr_deepspeech-jaco`](https://github.com/rhasspy/fr_deepspeech-jaco)
    * [`fr_kaldi-guyot`](https://github.com/synesthesiam/fr_kaldi-guyot) (default)
    * [`fr_kaldi-rhasspy`](https://github.com/rhasspy/fr_kaldi-rhasspy)
    * [`fr_pocketsphinx-cmu`](https://github.com/synesthesiam/fr_pocketsphinx-cmu)
* Hindi (`hi`)
    * [`hi_pocketsphinx-cmu`](https://github.com/synesthesiam/hi_pocketsphinx-cmu)
* Italian (`it`)
    * [`it_deepspeech-jaco`](https://github.com/rhasspy/it_deepspeech-jaco)
    * [`it_deepspeech-mozillaitalia`](https://github.com/rhasspy/it_deepspeech-mozillaitalia) (default)
    * [`it_kaldi-rhasspy`](https://github.com/rhasspy/it_kaldi-rhasspy)
    * [`it_pocketsphinx-cmu`](https://github.com/synesthesiam/it_pocketsphinx-cmu)
* Korean (`ko`)
    * [`ko-kr_kaldi-montreal`](https://github.com/synesthesiam/ko-kr_kaldi-montreal)
* Kazakh (`kz`)
    * [`kz_pocketsphinx-cmu`](https://github.com/synesthesiam/kz_pocketsphinx-cmu)
* Dutch (`nl`)
    * [`nl_kaldi-cgn`](https://github.com/synesthesiam/nl_kaldi-cgn) (default)
    * [`nl_kaldi-rhasspy`](https://github.com/rhasspy/nl_kaldi-rhasspy)
    * [`nl_pocketsphinx-cmu`](https://github.com/synesthesiam/nl_pocketsphinx-cmu)
* Polish (`pl`)
    * [`pl_deepspeech-jaco`](https://github.com/rhasspy/pl_deepspeech-jaco) (default)
    * [`pl_julius-github`](https://github.com/synesthesiam/pl_julius-github)
* Portuguese (`pt`)
    * [`pt-br_pocketsphinx-cmu`](https://github.com/synesthesiam/pt-br_pocketsphinx-cmu)
* Russian (`ru`)
    * [`ru_kaldi-rhasspy`](https://github.com/rhasspy/ru_kaldi-rhasspy) (default)
    * [`ru_pocketsphinx-cmu`](https://github.com/synesthesiam/ru_pocketsphinx-cmu)
* Swedish (`sv`)
    * [`sv_kaldi-montreal`](https://github.com/synesthesiam/sv_kaldi-montreal)
    * [`sv_kaldi-rhasspy`](https://github.com/rhasspy/sv_kaldi-rhasspy) (default)
* Vietnamese (`vi`)
    * [`vi_kaldi-montreal`](https://github.com/synesthesiam/vi_kaldi-montreal)
* Mandarin (`zh`)
    * [`zh-cn_pocketsphinx-cmu`](https://github.com/synesthesiam/zh-cn_pocketsphinx-cmu)

---

## Unique Features

`voice2json` is more than just a wrapper around open source speech to text systems!

* Training produces **both** a speech and intent recognizer. By describing your voice commands with `voice2json`'s [templating language](https://voice2json.org/sentences.html), you get [more than just transcriptions](https://voice2json.org/formats.html#intents) for free.
* Re-training is **fast enough** to be done at runtime (usually < 5s), even up to [millions of possible voice commands](https://voice2json.org/recipes.html#set-and-run-times). This means you can change [referenced slot](https://voice2json.org/sentences.html#slot-references) values or [add/remove intents](https://voice2json.org/commands.html#intent-whitelist) on the fly.
* All of the [available commands](#commands) are designed to work well in Unix pipelines, typically consuming/emitting plaintext or [newline-delimited JSON](http://jsonlines.org). Audio input/output is [file-based](https://voice2json.org/commands.html#audio-sources), so you can receive audio from [any source](https://voice2json.org/recipes.html#stream-microphone-audio-over-a-network).

## Commands

* [download-profile](https://voice2json.org/commands.html#download-profile) - Download missing files for a profile
* [train-profile](https://voice2json.org/commands.html#train-profile) - Generate speech/intent artifacts
* [transcribe-wav](https://voice2json.org/commands.html#transcribe-wav) - Transcribe WAV file to text
    * Add `--open` for unrestricted speech to text
* [transcribe-stream](https://voice2json.org/commands.html#transcribe-stream) - Transcribe live audio stream to text
    * Add `--open` for unrestricted speech to text
* [recognize-intent](https://voice2json.org/commands.html#recognize-intent) - Recognize intent from JSON or text
* [wait-wake](https://voice2json.org/commands.html#wait-wake) - Listen to live audio stream for wake word
* [record-command](https://voice2json.org/commands.html#record-command) - Record voice command from live audio stream
* [pronounce-word](https://voice2json.org/commands.html#pronounce-word) - Look up or guess how a word is pronounced
* [generate-examples](https://voice2json.org/commands.html#generate-examples) - Generate random intents
* [record-examples](https://voice2json.org/commands.html#record-examples) - Generate and record speech examples
* [test-examples](https://voice2json.org/commands.html#test-examples) - Test recorded speech examples
* [show-documentation](https://voice2json.org/commands.html#show-documentation) - Run HTTP server locally with documentation
* [print-profile](https://voice2json.org/commands.html#print-profile) - Print profile settings
* [print-downloads](https://voice2json.org/commands.html#print-downloads) - Print profile file download information
* [print-files](https://voice2json.org/commands.html#print-files) - Print user profile files for backup
