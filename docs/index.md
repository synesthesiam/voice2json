![voice2json logo](img/voice2json.svg)

`voice2json` is a collection of [command-line tools](commands.md) for <strong>offline speech/intent recognition</strong> on Linux. It is free, open source, and [supports 15 languages](#supported-languages). 

```bash
$ voice2json transcribe-wav < turn-on-the-light.wav | \
      voice2json recognize-text | \
      jq .
```

produces a [JSON event](formats.md) like:

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

when [trained](commands.md#train-profile) with this [template](sentences.md):

```ini
[LightState]
states = (on | off)
turn (<states>){state} [the] light
```

`voice2json` is <strong>optimized for</strong>:

* Sets of voice commands that are described well [by a grammar](sentences.md)
* Commands with [uncommon words or pronunciations](commands.md#pronounce-word)
* Commands or intents that [can vary at runtime](#unique-features)

It can be used to:

* Add voice commands to existing applications or Unix-style workflows
* Provide basic voice assistant functionality completely offline on modest hardware
* Bootstrap more sophisticated speech/intent recognition systems

---

## Unique Features

`voice2json` is more than just a wrapper around [pocketsphinx](https://github.com/cmusphinx/pocketsphinx) and [Kaldi](https://kaldi-asr.org)!

* Training produces **both** a speech and intent recognizer. By describing your voice commands with `voice2json`'s [templating language](sentences.md), you get [more than just transcriptions](formats.md#intents) for free.
* Re-training is **fast enough** to be done at runtime (usually < 10s), even up to millions of possible voice commands. This means

---

## How it Works

`voice2json` needs a description of the voice commands you want to be recognized in a file named `sentences.ini`. This can be as simple as a listing of intents and sentences:

```ini
[GarageDoor]
open the garage door
close the garage door

[LightState]
turn on the living room lamp
turn off the living room lamp
...
```

A small [templating language](sentences.md) is available to describe sets of valid voice commands, with `[optional words]`, `(alternative | choices)`, and `<shared rules>`. Portions of `(commands can be){annotated}` as containing slot values that you want in the recognized JSON.

When [trained](commands.md#train-profile), `voice2json` will transform [audio data](formats.md#audio) into [JSON objects](formats.md#intents) with the recognized <em>intent</em> and <em>slots</em>.

![Custom voice command training](img/overview-2.svg)

### Assumptions

voice2json is designed to work 

---

## Why Not That

Why not just use [Google](https://assistant.google.com/), [Dragon](https://www.nuance.com/dragon.html), or even [Snips](https://snips.ai/)?

### No Magic

---

## Getting Started

1. Install `voice2json`
2. Download a profile
3. Edit `sentences.ini`
4. Train your profile
5. See tutorials and recipes

---

## Supported Languages

voice2json supports the following languages/locales:

* Catalan
    * [ca-es_pocketsphinx-cmu](catalan/ca-es_pocketsphinx-cmu)
* Dutch (Nederlands)
    * [nl_pocketsphinx-cmu](dutch/nl_pocketsphinx-cmu)
* English
    * U.S. English
        * [en-us_pocketsphinx-cmu](english/en-us_pocketsphinx-cmu)
        * [en-us_kaldi-zamia](english/en-us_kaldi-zamia)
    * Indian English
        * [en-in_pocketsphinx-cmu](english/en-in_pocketsphinx-cmu)
* French (Français)
    * [fr_pocketsphinx-cmu](french/fr_pocketsphinx-cmu)
* German (Deutsch)
    * [de_pocketsphinx-cmu](german/de_pocketsphinx-cmu)
* Greek (Ελληνικά)
    * [el-gr_pocketsphinx-cmu](greek/el-gr_pocketsphinx-cmu)
* Hindi (Devanagari)
    * [hi_pocketsphinx-cmu](hindi/hi_pocketsphinx-cmu)
* Italian (Italiano)
    * [it_pocketsphinx-cmu](italian/it_pocketsphinx-cmu)
* Kazakh (қазақша)
    * [kz_pocketsphinx-cmu](kazakh/kz_pocketsphinx-cmu)
* Mandarin (中文)
    * [zh-cn_pocketsphinx-cmu](mandarin/zh-cn_pocketsphinx-cmu)
* Portugese (Português)
    * [pt-br_pocketsphinx-cmu](portuguese/pt-br_pocketsphinx-cmu)
* Russian (Русский)
    * [ru_pocketsphinx-cmu](russian/ru_pocketsphinx-cmu)
* Spanish (Español)
    * [es_pocketsphinx-cmu](spanish/es_pocketsphinx-cmu)
    * Mexian Spanish
        * [es_mexican_pocketsphinx-cmu](spanish/es_mexican_pocketsphinx-cmu)
* Swedish (svenska)
    * [sv_kaldi-montreal](swedish/sv_kaldi-montreal)
* Vietnamese (Tiếng Việt)
    * [vi_kaldi-montreal](vietnamese/vi_kaldi-montreal)
