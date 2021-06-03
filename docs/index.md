![voice2json logo](img/voice2json.svg)

`voice2json` is a collection of [command-line tools](commands.md) for <strong>offline speech/intent recognition</strong> on Linux. It is free, open source ([MIT](https://opensource.org/licenses/MIT)), and [supports 18 human languages](#supported-languages).

* [Getting Started](#getting-started)
* [Commands](commands.md)
    * [Data Formats](formats.md)
* [Profiles](https://github.com/synesthesiam/voice2json-profiles)
* [Recipes](recipes.md)
* [Node-RED Plugin](https://github.com/johanneskropf/node-red-contrib-voice2json)
* [About](about.md)
    * [Whitepaper](whitepaper.md)

From the command-line:

```bash
$ voice2json -p en transcribe-wav \
      < turn-on-the-light.wav | \
      voice2json -p en recognize-intent | \
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

Tools like [Node-RED](https://nodered.org) can be [easily integrated](recipes.md#create-an-mqtt-transcription-service) with `voice2json` through [MQTT](http://mqtt.org).

---

`voice2json` is <strong>optimized for</strong>:

* Sets of voice commands that are described well [by a grammar](sentences.md)
* Commands with [uncommon words or pronunciations](commands.md#pronounce-word)
* Commands or intents that [can vary at runtime](#unique-features)

It can be used to:

* Add voice commands to [existing applications or Unix-style workflows](recipes.md#create-an-mqtt-transcription-service)
* Provide basic [voice assistant functionality](recipes.md#set-and-run-timers) completely offline on modest hardware
* Bootstrap more [sophisticated speech/intent recognition systems](recipes.md#train-a-rasa-nlu-bot)

Supported speech to text systems include:

* CMU's [pocketsphinx](https://github.com/cmusphinx/pocketsphinx)
* Dan Povey's [Kaldi](https://kaldi-asr.org)
* Mozilla's [DeepSpeech](https://github.com/mozilla/DeepSpeech) 0.9
* Kyoto University's [Julius](https://github.com/julius-speech/julius)

---

## Getting Started

1. [Install voice2json](install.md)
2. Run [`voice2json -p <LANG> download-profile`](commands.md#download-profile) to download [language-specific](#supported-languages) files
    * Your [profile settings](profiles.md) will be in `$HOME/.local/share/voice2json/<PROFILE>/profile.yml`
3. Edit `sentences.ini` in [your profile](profiles.md) and add your [custom voice commands](sentences.md)
4. [Train your profile](commands.md#train-profile)
5. Use the [transcribe-wav](commands.md#transcribe-wav) and [recognize-intent](commands.md#recognize-intent) commands to do speech/intent recognition
    * See [the recipes](recipes.md) for more possibilities

---

## Supported Languages

`voice2json` supports the following languages/locales. I don't speak or write any language besides U.S. English very well, so **please** let me know if any profile is broken or could be improved! I'm mostly [Chinese Room-ing it](https://en.wikipedia.org/wiki/Chinese_room#Chinese_room_thought_experiment).

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

`voice2json` is more than just a wrapper around [pocketsphinx](https://github.com/cmusphinx/pocketsphinx), [Kaldi](https://kaldi-asr.org), [DeepSpeech](https://github.com/mozilla/DeepSpeech), and [Julius](https://github.com/julius-speech/julius)!

* Training produces **both** a speech and intent recognizer. By describing your voice commands with `voice2json`'s [templating language](sentences.md), you get [more than just transcriptions](formats.md#intents) for free.
* Re-training is **fast enough** to be done at runtime (usually < 5s), even up to [millions of possible voice commands](recipes.md#set-and-run-times). This means you can change [referenced slot](sentences.md#slot-references) values or [add/remove intents](commands.md#intent-whitelist) on the fly.
* All of the [available commands](commands.md) are designed to work well in **Unix pipelines**, typically consuming/emitting plaintext or [newline-delimited JSON](http://jsonlines.org). Audio input/output is [file-based](commands.md#audio-sources), so you can receive audio from [any source](recipes.md#stream-microphone-audio-over-a-network).

---

## How it Works

`voice2json` needs a description of the voice commands you want to be recognized in a file named `sentences.ini`. This can be as simple as a listing of `[Intents]` and sentences:

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

## Why Not That

Why not just use [Google](https://assistant.google.com/), [Dragon](https://www.nuance.com/dragon.html), or something else?

Cloud-based speech and intent recognition services, such as Google Assistant or Amazon's Alexa, require a constant Internet connection to function. Additionally, they keep a copy of everything you say on their servers. Despite the high accuracy and deep integration with other services, this approach is **too brittle and uncomfortable** for me.

Dragon Naturally Speaking offers local installations and offline functionality. Great! Unfortunately, Dragon requires Microsoft Windows to function. It is *possible* to use [Dragon in Wine on Linux](http://appdb.winehq.org/objectManager.php?sClass=application&iId=2077) or via a virtual machine, but is difficult to set up and not officially supported by [Nuance](https://www.nuance.com).

Until relatively recently, [Snips](https://snips.ai) offered an impressive amount of functionality offline and was [easy to interoperate with](https://docs.snips.ai/reference/hermes). Unfortunately, they were [purchased by Sonos](https://investors.sonos.com/news-and-events/investor-news/latest-news/2019/Sonos-Announces-Acquisition-of-Snips/default.aspx) and have since shut down their online services (required to change your Snips assistants). See [Rhasspy](https://github.com/rhasspy) if you are looking for a Snips replacement, and avoid investing time and effort in a platform you cannot control!

If you feel comfortable sending your voice commands through the Internet for someone else to process, or are not comfortable with Linux and the command line, I recommend taking a look at [Mycroft](https://mycroft.ai).

### No Magic, No Surprises

`voice2json` is **not an A.I.** or gee-whizzy machine learning system. It does not attempt to guess what you want to do, and keeps **everything** on your local machine. There is no online account sign-up needed, **no privacy policy** to review, and no advertisements. All generated artifacts are in [standard data formats](formats.md); typically just text.

Once you've [installed voice2json](install.md) and [downloaded a profile](install.md#download-profile), there is no longer a need for an Internet connection. At runtime, `voice2json` will only every write to your [profile directory](profiles.md) or the system's temporary directory (`/tmp`).

---

---

## Contributing

Community contributions are welcomed! There are many different ways to contribute:

* Pull requests for bug fixes, new features, or corrections to the documentation
* Help with any of the [supported language profiles](#supported-languages), including:
    * Testing to make sure the acoustic models and default pronunciation dictionaries are working
    * Translations of the [example voice commands](https://github.com/synesthesiam/en-us_pocketsphinx-cmu/blob/8e6c984183a43de0cc87930efff37b4a5c840a40/sentences.ini)
    * Example WAV files of you speaking with text transcriptions for performance testing
* [Contributing to Mozilla Common Voice](https://voice.mozilla.org/)
* Assist other `voice2json` [community members](https://community.rhasspy.org/c/voice2json/10)
* Implement or critique one of [my crazy ideas](#ideas)

---

## Ideas

Here are some ideas I have for making `voice2json` better that I don't have time to implement.

### Yet Another Wake Word Library

[Porcupine](https://github.com/Picovoice/Porcupine) is the best free wake word library I've found to date, but it has two major limitations for me:

1. It is not entirely open source
    * I can't build it for architecture that aren't currently supported
2. Custom wake words expire after 30 days
    * I can't include custom wake words in pre-built packages/images
    
[Picovoice](https://picovoice.ai) has been very generous to release porcupine for free, so I'm not suggesting they change anything. Instead, I'd love to see a free and open source wake word library that has these features:

* Free and completely open source
* Performance *close* to porcupine or [snowboy](https://snowboy.kitt.ai)
* Able to run on a Raspberry Pi alongside other software (no 100% CPU usage)
* Can add custom wake words without hours of training

[Mycroft Precise](https://github.com/MycroftAI/mycroft-precise) comes close, but requires a lot of expertise and time to train custom wake words. It's performance is also unfortunately poorer than porcupine (in my limited experience).

I've wondered if Mycroft Precise's approach ([a GRU](https://github.com/MycroftAI/mycroft-precise#how-it-works)) could be extended to include Pocketsphinx's [keyword search mode](https://cmusphinx.github.io/wiki/tutoriallm/#using-keyword-lists-with-pocketsphinx) as an input feature during training and at runtime. On it's own, Pocketsphinx's performance as a wake word detector [is abysmal](https://github.com/Picovoice/wake-word-benchmark#results). But perhaps as one of several features in a neural network, it could help more than hurt.

### Acoustic Models From Audiobooks

The paper [LibriSpeech: An ASR Corpus Based on Public Domain Audio Books](http://www.danielpovey.com/files/2015_icassp_librispeech.pdf) describes a method for taking free audio books from [LibriVox](https://librivox.org) and training [acoustic models](whitepaper.md#acoustic-model) from it using [Kaldi](https://kaldi-asr.org). For languages besides English, this may be a way of getting around the lack of free transcribed audio datasets! Although not ideal, it's better than nothing.

For some languages, the audiobook approach may be especially useful with end-to-end machine learning approaches, like [Mozilla's DeepSpeech](https://github.com/mozilla/DeepSpeech) and [Facebook's wav2letter](https://github.com/facebookresearch/wav2letter). Typical approaches to building acoustic models require the identification of a language's phonemes and the construction of a large [pronunciation dictionary](whitepaper.md#pronunciation-dictionary). End-to-end approaches go directly from acoustic features to graphemes (letters), subsuming the phonetic dictionary step. More data is required, of course, but books tend to be quite long.

### Android Support

`voice2json` uses [pocketsphinx](https://github.com/cmusphinx/pocketsphinx), [Kaldi](https://kaldi-asr.org), and [Julius](https://github.com/julius-speech/julius) for speech recognition. All of these libraries have at least a proof-of-concept Android build:

* [Pocketsphinx on Android](https://cmusphinx.github.io/wiki/tutorialandroid/)
* [Compile Kaldi for Android](http://jcsilva.github.io/2017/03/18/compile-kaldi-android/)
* [Julius on Android](https://github.com/julius-speech/julius/speech/104)

It seems feasible that `voice2json` could be ported to Android, providing decent offline mobile speech/intent recognition.

### Browser-Based voice2json

Could [empscripten](https://empscripten.org) be used to compile WebAssembly versions of `voice2json`'s dependencies? Combined with something like [pyodide](https://github.com/iodide-project/pyodide), it might be possible to run (most of) `voice2json` entirely in a modern web browser.

---

![smiling terminal](img/terminal.svg)
