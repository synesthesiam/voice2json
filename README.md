![voice2json logo](docs/img/voice2json.svg)

`voice2json` is a collection of [command-line tools](#commands) for <strong>offline speech/intent recognition</strong> on Linux. It is free, open source, and [supports 15 languages](#supported-languages). 

* [Documentation](https://voice2json.readthedocs.io/en/latest)
* [Download](https://github.com/synesthesiam/voice2json/releases)
* [Docker Install](https://voice2json.readthedocs.io/en/latest/install/#docker-image)

From the command-line:

```bash
$ voice2json transcribe-wav < turn-on-the-light.wav | \
      voice2json recognize-intent | \
      jq .
```

produces a [JSON event](https://voice2json.readthedocs.io/en/latest/formats/) like:

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

when trained with this [template](https://voice2json.readthedocs.io/en/latest/sentences/):

```ini
[LightState]
states = (on | off)
turn (<states>){state} [the] light
```

`voice2json` is <strong>optimized for</strong>:

* Sets of voice commands that are described well [by a grammar](https://voice2json.readthedocs.io/en/latest/sentences/)
* Commands with [uncommon words or pronunciations](https://voice2json.readthedocs.io/en/latest/commands/#pronounce-word)
* Commands or intents that [can vary at runtime](#unique-features)

It can be used to:

* Add voice commands to [existing applications or Unix-style workflows](https://voice2json.readthedocs.io/en/latest/recipes/#create-an-mqtt-transcription-service)
* Provide basic [voice assistant functionality](https://voice2json.readthedocs.io/en/latest/recipes/#set-and-run-timers) completely offline on modest hardware
* Bootstrap more [sophisticated speech/intent recognition systems](https://voice2json.readthedocs.io/en/latest/recipes/#train-a-rasa-nlu-bot)

---

## Unique Features

`voice2json` is more than just a wrapper around [pocketsphinx](https://github.com/cmusphinx/pocketsphinx) and [Kaldi](https://kaldi-asr.org)!

* Training produces **both** a speech and intent recognizer. By describing your voice commands with `voice2json`'s [templating language](https://voice2json.readthedocs.io/en/latest/sentences/), you get [more than just transcriptions](https://voice2json.readthedocs.io/en/latest/formats/#intents) for free.
* Re-training is **fast enough** to be done at runtime (usually < 5s), even up to [millions of possible voice commands](https://voice2json.readthedocs.io/en/latest/recipes/#set-and-run-times). This means you can change [referenced slot](https://voice2json.readthedocs.io/en/latest/sentences/#slot-references) values or [add/remove intents](https://voice2json.readthedocs.io/en/latest/commands/#intent-whitelist) on the fly.
* All of the [available commands](#commands) are designed to work well in Unix pipelines, typically consuming/emitting plaintext or [newline-delimited JSON](http://jsonlines.org). Audio input/output is [file-based](https://voice2json.readthedocs.io/en/latest/commands/#audio-sources), so you receive audio from [any source](https://voice2json.readthedocs.io/en/latest/recipes/#stream-microphone-audio-over-a-network).

## Commands

* [print-profile](https://voice2json.readthedocs.io/en/latest/commands/#print-profile) - Print profile settings
* [train-profile](https://voice2json.readthedocs.io/en/latest/commands/#train-profile) - Generate speech/intent artifacts
* [transcribe-wav](https://voice2json.readthedocs.io/en/latest/commands/#transcribe-wav) - Transcribe WAV file to text
* [recognize-intent](https://voice2json.readthedocs.io/en/latest/commands/#recognize-intent) - Recognize intent from JSON or text
* [wait-wake](https://voice2json.readthedocs.io/en/latest/commands/#wait-wake) - Listen to live audio stream for wake word
* [record-command](https://voice2json.readthedocs.io/en/latest/commands/#record-command) - Record voice command from live audio stream
* [pronounce-word](https://voice2json.readthedocs.io/en/latest/commands/#pronounce-word) - Look up or guess how a word is pronounced
* [generate-examples](https://voice2json.readthedocs.io/en/latest/commands/#generate-examples) - Generate random intents
* [record-examples](https://voice2json.readthedocs.io/en/latest/commands/#record-examples) - Generate and record speech examples
* [test-examples](https://voice2json.readthedocs.io/en/latest/commands/#test-examples) - Test recorded speech examples
* [tune-examples](https://voice2json.readthedocs.io/en/latest/commands/#tune-examples) - Tune acoustic model using recorded speech examples

## Supported Languages

`voice2json` supports the following languages/locales:

* Catalan
    * [ca-es_pocketsphinx-cmu](https://github.com/synesthesiam/ca-es_pocketsphinx-cmu)
* Dutch (Nederlands)
    * [nl_pocketsphinx-cmu](https://github.com/synesthesiam/nl_pocketsphinx-cmu)
* English
    * U.S. English
        * [en-us_pocketsphinx-cmu](https://github.com/synesthesiam/en-us_pocketsphinx-cmu)
        * [en-us_kaldi-zamia](https://github.com/synesthesiam/en-us_kaldi-zamia)
    * Indian English
        * [en-in_pocketsphinx-cmu](https://github.com/synesthesiam/en-in_pocketsphinx-cmu)
* French (Français)
    * [fr_pocketsphinx-cmu](https://github.com/synesthesiam/fr_pocketsphinx-cmu)
* German (Deutsch)
    * [de_pocketsphinx-cmu](https://github.com/synesthesiam/de_pocketsphinx-cmu)
* Greek (Ελληνικά)
    * [el-gr_pocketsphinx-cmu](https://github.com/synesthesiam/el-gr_pocketsphinx-cmu)
* Hindi (Devanagari)
    * [hi_pocketsphinx-cmu](https://github.com/synesthesiam/hi_pocketsphinx-cmu)
* Italian (Italiano)
    * [it_pocketsphinx-cmu](https://github.com/synesthesiam/it_pocketsphinx-cmu)
* Kazakh (қазақша)
    * [kz_pocketsphinx-cmu](https://github.com/synesthesiam/kz_pocketsphinx-cmu)
* Mandarin (中文)
    * [zh-cn_pocketsphinx-cmu](https://github.com/synesthesiam/zh-cn_pocketsphinx-cmu)
* Portugese (Português)
    * [pt-br_pocketsphinx-cmu](https://github.com/synesthesiam/pt-br_pocketsphinx-cmu)
* Russian (Русский)
    * [ru_pocketsphinx-cmu](https://github.com/synesthesiam/ru_pocketsphinx-cmu)
* Spanish (Español)
    * [es_pocketsphinx-cmu](https://github.com/synesthesiam/es_pocketsphinx-cmu)
    * Mexian Spanish
        * [es_mexican_pocketsphinx-cmu](https://github.com/synesthesiam/es_mexican_pocketsphinx-cmu)
* Swedish (svenska)
    * [sv_kaldi-montreal](https://github.com/synesthesiam/sv_kaldi-montreal)
* Vietnamese (Tiếng Việt)
    * [vi_kaldi-montreal](https://github.com/synesthesiam/vi_kaldi-montreal)
