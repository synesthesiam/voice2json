# Command-Line Tools

```bash
$ voice2json [--debug] [--profile <PROFILE_DIR>] <COMMAND> [<COMMAND_ARG>...]
```

The [profile](profiles.md) directory can be given with `--profile`. If not provided, a profile is expected in `$XDG_CONFIG_HOME/voice2json`, which is typically `$HOME/.config/voice2json`.

The following commands are available:

* [print-profile](#print-profile) - Print profile settings
* [train-profile](#train-profile) - Generate speech/intent artifacts
* [transcribe-wav](#transcribe-wav) - Transcribe WAV file to text
* [recognize-text](#recognize-text) - Recognize intent from text
* [wait-wake](#wait-wake) - Listen to live audio stream for wake word
* [record-command](#record-command) - Record voice command from live audio stream
* [pronounce-word](#pronounce-word) - Look up or guess how a word is pronounced
* [generate-examples](#generate-examples) - Generate random intents
* [record-examples](#record-examples) - Generate and record speech examples
* [test-examples](#test-examples) - Test recorded speech examples
* [tune-examples](#tune-examples) - Tune acoustic model using recorded speech examples
    
---

## print-profile

Prints all profile settings as JSON to the console. This is a combination of the [default settings](profiles.md#default-settings) and what's provided in [profile.yml](profiles.md#profileyml).

```bash
$ voice2json print-profile | jq .
```

Output:

```json
{
    "language": {
        "name": "english",
        "code": "en-us"
    },
    "speech-to-text": {
        ...
    },
    "intent-recognition": {
        ...
    },
    "training": {
        ...
    },
    "wake-word": {
        ...
    },
    "voice-command": {
        ...
    },
    "text-to-speech": {
        ...
    },
    "audio": {
        ...
    },

    ...
}
```

---

## train-profile

Generates all necessary artifacts in a [profile](profiles.md) for speech/intent recognition.

```bash
$ voice2json train-profile
```

Output:

```
. grammars
. grammar_dependencies:GetTemperature_dependencies
. grammar_dependencies:ChangeLightColor_dependencies
. grammar_dependencies:GetGarageState_dependencies
. grammar_dependencies:GetTime_dependencies
. grammar_dependencies:ChangeLightState_dependencies
. grammar_fsts:GetTemperature_fst
. grammar_fsts:GetGarageState_fst
. grammar_fsts:GetTime_fst
. grammar_fsts:slot_fsts
. grammar_fsts:ChangeLightColor_fst
. grammar_fsts:ChangeLightState_fst
. intent_fst
. language_model:intent_counts
. language_model:intent_model
. language_model:intent_arpa
. vocab
. vocab_dict
```

`voice2json` uses [doit](https://pydoit.org) to orchestrate the generation of profile artifacts. Doit is similar to `make`, so only those artifacts that have changed are rebuilt.

Settings that control where generated artifacts are saved are in the `training` section of your [profile](profiles.md).

### Slots Directory

If your [sentences.ini](sentences.md) file contains [slot references](sentences.md#slot-references), `voice2json` will look for text files in a directory named `slots` in your profile (set `training.slots-directory` to change). If you reference `$movies`, then `slots/movies` should exist with one item per line. When these files change, you should [re-train](#train-profile).

### Intent Whitelist

If a file named `intent_whitelist` exists in your profile (set `training.intent-whitelist` to change), then `voice2json` will only consider the intents listed in it (one per line). If this file is missing (the default), then all intents from [sentences.ini](sentences.md) are considered. When this file changes, you should [re-train](#train-profile).

### Language Model Mixing

TODO

---

## transcribe-wav

Transcribes WAV file(s) or raw audio data. Outputs a single line of [jsonl](http://jsonlines.org) for each transcription ([format description](formats.md#transcriptions)).

### WAV data from stdin

Reads a WAV file from standard in and transcribes it.

```bash
$ voice2json transcribe-wav < turn-on-the-light.wav
```

Output:


```json
{"text": "turn on the light", "transcribe_seconds": 0.123, "wav_seconds": 1.456}
```

**Note**: No `wav_name` property is provided when WAV data comes from standard in.

### Files as arguments

Reads one or more WAV files and transcribes each of them in turn.

```bash
$ voice2json transcribe-wav \
      turn-on-the-light.wav \
      what-time-is-it.wav
```

Output:


```json
{"text": "turn on the light", "transcribe_seconds": 0.123, "wav_seconds": 1.456, "wav_name": "turn-on-the-light.wav"}
{"text": "what time is it", "transcribe_seconds": 0.123, "wav_seconds": 1.456, "wav_name": "what-time-is-it.wav"}
```

### Files from stdin

Reads one or more WAV file paths from standard in and transcribes each of them in turn. If arguments are also provided, they will be processed **first**.

```bash
$ voice2json transcribe-wav --stdin-files
turn-on-the-light.wav
what-time-is-it.wav
<CTRL-D>
```

Output:


```json
{"text": "turn on the light", "transcribe_seconds": 0.123, "wav_seconds": 1.456, "wav_name": "turn-on-the-light.wav"}
{"text": "what time is it", "transcribe_seconds": 0.123, "wav_seconds": 1.456, "wav_name": "what-time-is-it.wav"}
```

### Open Transcription

When given the `--open` argument, `transcribe-wav` will ignore your [custom voice commands](sentences.md) and instead use the large, pre-trained speech model present in [your profile](profiles.md). Do this if you want to use `voice2json` for general transcription tasks that are not domain specific. Keep in mind, of course, that this is not what `voice2json` is optimized for!

If you want the best of both worlds (transcriptions focused on a particular domain, but still able to accomodate general speech), check out [language model mixing](#language-model-mixing). This comes at a performance cost, however, in training, loading, and transcription times. Consider using `transcribe-wav` [as a service](recipes.md#create-an-mqtt-transcription-service) to avoid re-loading your mixed speech model.

---

## recognize-text

Recognizes an intent and slots from JSON or plaintext. Outputs a single line of [jsonl](http://jsonlines.org) for each input line ([format description](formats.md#intents)).

Inputs can be provided either as arguments **or** lines via standard in.

### JSON input

Input is a single line of [jsonl](http://jsonlines.org) per sentence, minimally with a `text` property (like the output of [transcribe-wav](#transcribe-wav)).

```bash
voice2json recognize-text '{ "text": "turn on the light" }'
```

Output:

```json
{"text": "turn on the living room lamp", "intent": {"name": "LightState", "confidence": 1.0}, "entities": [{"entity": "state", "value": "on"}], "slots": {"state": "on"}, "recognize_seconds": 0.001}
```

### Plaintext input

Input is a single line of plaintext per sentence.

```bash
voice2json recognize-text --text-input 'turn on the light' 'turn off the light'
```

Output:

```json
{"text": "turn on the living room lamp", "intent": {"name": "LightState", "confidence": 1.0}, "entities": [{"entity": "state", "value": "on"}], "slots": {"state": "on"}, "recognize_seconds": 0.001}
{"text": "turn off the living room lamp", "intent": {"name": "LightState", "confidence": 1.0}, "entities": [{"entity": "state", "value": "off"}], "slots": {"state": "off"}, "recognize_seconds": 0.001}
```

---

## wait-wake

Listens to a live audio stream for a wake word (default is "[porcupine](https://github.com/Picovoice/Porcupine)"). Outputs a single line of [jsonl](http://jsonlines.org) each time the wake word is detected.

```bash
$ voice2json wait-wake
```

Once the wake word is spoken, `voice2json` will output:

```json
{ "keyword": "/path/to/keyword.ppn", "detect_seconds": 1.2345 }
```

where `keyword` is the path to the detected keyword file and `detect_seconds` is the time of detection relative to when `voice2json` was started.

### Custom Wake Word

You can [train your own wake word](https://github.com/Picovoice/Porcupine#picovoice-console) or use [one of the pre-trained keyword files](https://github.com/Picovoice/porcupine/tree/master/resources/keyword_files) from [Picovoice](https://picovoice.ai/).

### Exit Count

Providing a `--exit-count <N>` argument to `wait-wake` tells `voice2json` to automatically exit after the wake word has been detected `N` times. This is useful when you want to use `wait-wake` in [a shell script](recipes.md#launch-a-program-via-voice).


### Audio Sources

By default, the [wait-wake](#wait-wake), [record-command](#record-command), and [record-examples](#record-examples) commands execute the program defined in the `audio.record-command` section of [your profile](profiles.md) to record audio. You can customize/change this program or provide a different source of [audio data](formats.md#audio) with the `--audio-source` argument, which expects a file path or "-" for standard in. Through [process substition](https://www.gnu.org/software/bash/manual/html_node/Process-Substitution.html) or Unix pipes, this can be used to receive [microphone audio streamed over a network](recipes.md#stream-microphone-audio-over-a-network).

---

## record-command

Records from a live audio stream until a voice command has been spoken.

TODO

See [audio sources](#audio-sources) for a description of how `record-command` gets audio input.

---

## pronounce-word

Uses [eSpeak](http://espeak.sourceforge.net) to pronounce words *the same way that the speech recognizer is expecting them*. This depends on manually created [phoneme map](formats.md#espeak-phoneme-maps) in each profile.

Inputs can be provided either as arguments **or** lines via standard in.

Assuming you're using the `en-us_pocketsphinx-cmu` profile:

```bash
voice2json pronounce-word hello
```

Output:

```
hello HH AH L OW
hello HH EH L OW

```

In addition to text output, you should have heard both pronunciations of "hello". These came the `base_dictionary.txt` included in the profile.

### Unknown Words

The same `pronounce-word` command works for words that are hopefully **not** in the U.S. English dictionary:

```bash
voice2json pronounce-word raxacoricofallipatorius
```

Output:

```
raxacoricofallipatorius R AE K S AH K AO R IH K AO F AE L AH P AH T AO R IY IH S
raxacoricofallipatorius R AE K S AH K AO R IY K OW F AE L AH P AH T AO R IY IH S
raxacoricofallipatorius R AE K S AH K AO R AH K OW F AE L AH P AH T AO R IY IH S
raxacoricofallipatorius R AE K S AH K AA R IH K AO F AE L AH P AH T AO R IY IH S
raxacoricofallipatorius R AE K S AH K AO R IH K OW F AE L AH P AH T AO R IY IH S
```

This produced 5 pronunciation guesses using [phonetisaurus](https://github.com/AdolfVonKleist/Phonetisaurus) and the grapheme-to-phoneme model provided with the profile (`g2p.fst`).

If you want to hear a specific pronunciation, just provide it with the word:

```bash
voice2json pronounce-word 'moogle M UW G AH L' 
```

You can save these pronunciations in the `custom_words.txt` file in your [profile](profiles.md). Make sure to [re-train](#train-profile).

---

## generate-examples

Generates random intents and slots from your [profile](profiles.md). Outputs a single line of [jsonl](http://jsonlines.org) for each intent line ([format description](formats.md#intents)).

```bash
$ voice2json generate-examples --count 1 | jq .
```

Output (formatted with [jq](https://stedolan.github.io/jq/)):

```json
{
  "text": "turn on the light",
  "intent": {
    "name": "LightState",
    "confidence": 1
  },
  "entities": [
    {
      "entity": "state",
      "value": "on",
      "start": 5,
      "end": 7
    }
  ],
  "slots": {
    "state": "off"
  },
  "tokens": [
      "turn",
      "on",
      "the",
      "light"
  ]
}
```

### IOB Format

If the `--iob` argument is given, `generate-examples` will output examples in an inside-outside-beginning format with 3 tab-separated sections:

1. The words themselves surround by `BS` (begin sentence) and `ES` tokens
2. The tag for each word, one of `O` (outside), `B-<NAME>` (begin `NAME`), `I-<NAME>` (inside `NAME`)
3. The intent name

```bash
$ voice2json generate-examples --count 1 --iob
```

Output:


```
BS turn off the light ES<TAB>O O B-state O O O<TAB>LightState
```

### Other Formats

See the [Rasa NLU bot recipe](recipes.md#train-a-rasa nlu-bot) for an example of transforming `voice2json` examples into Rasa NLU's [Markdown training data format](https://rasa.com/docs/rasa/nlu/training-data-format/).

---

## record-examples

TODO

---

## test-examples

TODO

---

## tune-examples

Pocketsphinx only.

TODO
