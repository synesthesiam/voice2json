![voice2json logo](img/voice2json.svg)

`voice2json` is a collection of [command-line tools](commands.md) for <strong>offline speech/intent recognition</strong> on Linux. It is free, open source, and [supports 15 languages](#supported-languages). 

* [Getting Started](#getting-started)
* [Commands](commands.md)
* [Recipes](recipes.md)
* [About](about.md)

From the command-line:

```bash
$ voice2json transcribe-wav \
      < turn-on-the-light.wav | \
      voice2json recognize-intent | \
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

```
[LightState]
states = (on | off)
turn (<states>){state} [the] light
```

`voice2json` is <strong>optimized for</strong>:

* Sets of voice commands that are described well [by a grammar](sentences.md)
* Commands with [uncommon words or pronunciations](commands.md#pronounce-word)
* Commands or intents that [can vary at runtime](#unique-features)

It can be used to:

* Add voice commands to [existing applications or Unix-style workflows](recipes.md#create-an-mqtt-transcription-service)
* Provide basic [voice assistant functionality](recipes.md#set-and-run-timers) completely offline on modest hardware
* Bootstrap more [sophisticated speech/intent recognition systems](recipes.md#train-a-rasa-nlu-bot)

---

## Unique Features

`voice2json` is more than just a wrapper around [pocketsphinx](https://github.com/cmusphinx/pocketsphinx), [Kaldi](https://kaldi-asr.org), and [Julius](https://github.com/julius-speech/julius)!

* Training produces **both** a speech and intent recognizer. By describing your voice commands with `voice2json`'s [templating language](sentences.md), you get [more than just transcriptions](formats.md#intents) for free.
* Re-training is **fast enough** to be done at runtime (usually < 5s), even up to [millions of possible voice commands](recipes.md#set-and-run-times). This means you can change [referenced slot](sentences.md#slot-references) values or [add/remove intents](commands.md#intent-whitelist) on the fly.
* All of the [available commands](commands.md) are designed to work well in Unix pipelines, typically consuming/emitting plaintext or [newline-delimited JSON](http://jsonlines.org). Audio input/output is [file-based](commands.md#audio-sources), so you receive audio from [any source](recipes.md#stream-microphone-audio-over-a-network).

---

## How it Works

`voice2json` needs a description of the voice commands you want to be recognized in a file named `sentences.ini`. This can be as simple as a listing of intents and sentences:

```
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

`voice2json` is designed to work under the following assumptions:

* Speech can be segmented into voice commands by a [wake word](commands.md#wait-wake) + [silence](commands.md#record-command), or via a push-to-talk mechanism
* A voice commands contains at most **one intent**
* Intents and [slot values](sentences.md#slot-references) are equally likely

---

## Getting Started

1. [Install voice2json](install.md)
2. [Download a profile](https://github.com/synesthesiam/voice2json-profiles) and extract it to `$HOME/.config/voice2json`
    * Your [profile settings](profiles.md) will be in `$HOME/.config/voice2json/profile.yml`
3. Edit `sentences.ini` in [your profile](profiles.md) and add your [custom voice commands](sentences.md)
4. [Train your profile](commands.md#train-profile)
5. Use the [transcribe-wav](commands.md#transcribe-wav) and [recognize-intent](commands.md#recognize-intent) commands to do speech/intent recognition
    * See [the recipes](recipes.md) for more possibilities

---

## Why Not That

Why not just use [Google](https://assistant.google.com/), [Dragon](https://www.nuance.com/dragon.html), or even [Snips](https://snips.ai/)?

Cloud-based speech and intent recognition services, such as Google Assistant or Amazon's Alexa, require a constant Internet connection to function. Additionally, they keep a copy of everything you say on their servers. Despite the high accuracy and deep integration with other services, this approach is **too brittle and uncomfortable** for me.

Dragon Naturally Speaking and Snips offer local installations and offline functionality. Unfortunately, Dragon requires Microsoft Windows to function. It is *possible* to use [Dragon in Wine on Linux](http://appdb.winehq.org/objectManager.php?sClass=application&iId=2077) or via a virtual machine, but is difficult to set up and not officially supported by [Nuance](https://www.nuance.com). Snips offers an impressive amount of functionality and is [easy to interoperate with](https://docs.snips.ai/reference/hermes), but [requires an online account](https://console.snips.ai/login) just to create an assistant. Additionally, Snips is not yet fully open source, so any artifacts created for a Snips-based assistant may **not be portable** to another platform in the future.

### No Magic, No Surprises

`voice2json` is **not an A.I.**. It does not attempt to guess what you want to do, and keeps **everything** on your local machine. There is no online account sign-up needed, **no privacy policy** to review, and no advertisements. All generated artifacts are in [standard data formats](formats.md); typically just text.

Once you've [installed voice2json](install.md) and [downloaded a profile](install.md#download-profile), there is no longer a need for an Internet connection. At runtime, `voice2json` will only every write to your [profile directory](profiles.md) or the system's temporary directory (`/tmp`).

---

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
* Polish (polski)
    * [pl_julius-github](https://github.com/synesthesiam/pl_julius-github)
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

## Contributing

Community contributions are welcomed! There are many different ways to contribute:

* Pull requests for bug fixes, new features, or corrections to the documentation
* Help with each of the [supported language profiles](#supported-languages)
    * Testing to make sure the acoustic models and default pronunciation dictionaries are working
    * Translations of the [example voice commands](https://github.com/synesthesiam/en-us_pocketsphinx-cmu/blob/8e6c984183a43de0cc87930efff37b4a5c840a40/sentences.ini)
    * Example of you speaking with transcriptions
* Help with adding support for a different language by [contributing to Mozilla Common Voice](https://voice.mozilla.org/)
* TODO Assist community members
* Implement one of [my crazy ideas](#ideas)

## Ideas

### Yet Another Wake Word Library

TODO

### Acoustic Models From Audiobooks

TODO

### Android Support

TODO

### Browser Based Pocketsphinx

TODO

---

![smiling terminal](img/terminal.svg)
