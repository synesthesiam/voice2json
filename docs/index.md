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

`voice2json` is <strong>optimized for</strong>:

* Voice command domains that are well described [by a grammar](sentences.md)
* Uncommon words or pronunciations
* Vocabulary that varies at runtime

It can be used to:

* Add voice commands to existing applications
* Provide basic voice assistant functionality
* Bootstrap more sophisticated speech/intent systems

---

* [How it Works](#how-it-works)
* [Why Not](#why-not)
* [Getting Started](#getting-started)
* [Supported Languages](#supported-languages)
* [License](about.md#license)

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

## Why Not

Why not Google

### No Magic

---

## Getting Started

### Debian

### Docker

### Source

---

## Supported Languages

voice2json currently supports the following languages/locales:

* Catalan
    * [ca-es_pocketsphinx-cmu](catalan/ca-es_pocketsphinx-cmu)
* Dutch (Nederlands)
    * [nl_pocketsphinx-cmu](dutch/nl_pocketsphinx-cmu)
        * Status: **Verified**
* English
    * U.S. English
        * [en-us_pocketsphinx-cmu](english/en-us_pocketsphinx-cmu)
            * Status: **Verified**
        * [en-us_kaldi-zamia](english/en-us_kaldi-zamia)
            * Status: **Verified**
    * Indian English
        * [en-in_pocketsphinx-cmu](english/en-in_pocketsphinx-cmu)
* French (Français)
    * [fr_pocketsphinx-cmu](french/fr_pocketsphinx-cmu)
        * Status: **Verified**
* German (Deutsch)
    * [de_pocketsphinx-cmu](german/de_pocketsphinx-cmu)
        * Status: **Verified**
* Greek (Ελληνικά)
    * [el-gr_pocketsphinx-cmu](greek/el-gr_pocketsphinx-cmu)
* Hindi (Devanagari)
    * [hi_pocketsphinx-cmu](hindi/hi_pocketsphinx-cmu)
* Italian (Italiano)
    * [it_pocketsphinx-cmu](italian/it_pocketsphinx-cmu)
        * Status: **Verified**
* Kazakh (қазақша)
    * [kz_pocketsphinx-cmu](kazakh/kz_pocketsphinx-cmu)
* Mandarin (中文)
    * [zh-cn_pocketsphinx-cmu](mandarin/zh-cn_pocketsphinx-cmu)
* Portugese (Português)
    * [pt-br_pocketsphinx-cmu](portuguese/pt-br_pocketsphinx-cmu)
        * Status: **Verified**
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
