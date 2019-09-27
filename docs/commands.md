# Command-Line Tools

```bash
$ voice2json [--debug] [--profile <PROFILE_DIR>] <COMMAND> [<COMMAND_ARG>...]
```

The [profile](profiles.md) directory can be given with `--profile`. If not provided, a profile is expected in `$XDG_CONFIG_HOME/voice2json`, which is typically `$HOME/.config/voice2json`.

The following commands are available:

* [print-profile](#print-profile) - Print profile settings
* [train-profile](#train-profile) - Generate speech/intent artifacts
* [transcribe-wav](#transcribe-wav) - Transcribe WAV file to text
* [recognize-intent](#recognize-intent) - Recognize intent from JSON or text
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

`voice2json` is designed to only recognize the voice commands you specify in [sentences.ini](sentences.md). Both the [pocketsphinx](https://github.com/cmusphinx/pocketsphinx) and [Kaldi](https://kaldi-asr.org) speech systems are capable of transcribing [open-ended speech](#open-transcription), however. But what if you want to recognize *sort of* open-ended speech that's still focused on [your voice commands](sentences.md)?

In every [profile](profiles.md), `voice2json` includes a `base_dictionary.txt` and `base_language_model.txt` file. The former is a dictionary containing the pronunciations all possible words. The latter is a large language model trained on *very* large corpus of text in the profile's language (usually books and web pages).

During training, `voice2json` can **mix** the large, open ended language model in `base_language_model.txt` with the one generated specifically for your voice commands. You specify a **mixture weight**, which controls how much of an influence the large language model has (see `training.base-language-model-weight`). A mixture weight of 0 makes `voice2json` sensitive *only* to your voice commands, which is the default. A mixture weight of 0.05, on the other hand, adds a 5% influence from the large language model.

![Diagram of training process](img/training.svg)

To see the effect of language model mixing, consder a simple `sentences.ini` file:

```ini
[ChangeLightState]
turn (on){state} the living room lamp
```

This will only allow `voice2json` to recognize the voice command "turn on the living room lamp". If we train `voice2json` and [transcribe](#transcribe-wav) a WAV file with this command, the output is no surprise:

```bash
$ time voice2json train-profile
...
real	0m0.688s

$ voice2json transcribe-wav \
    turn_on_living_room_lamp.wav | \
    jq -r .text

turn on the living room lamp
```

Now let's do speech to text on a variation of the command, a WAV file with the speech "would you please turn on the living room lamp":

```bash
$ voice2json transcribe-wav \
    would_you_please_turn_on_living_room_lamp.wav | \
    jq -r .text
    
turn the turn on the living room lamp
```

The word salad here is because we're trying to recognize a voice command that was not present in `sentences.ini` (technically, it's because [n-gram models are kind of dumb](whitepaper.md#sentences)). We could always add it to `sentences.ini`, of course. There may be cases, however, where we cannot anticipate *all* of the variations of a voice command. For these cases, you should increase the `training.base-language-model-weight` in your [profile](profiles.md) to something above 0. Let's set it to 0.05 (5% mixture) and re-train:

```bash
$ time voice2json train-profile
...
real	1m3.221s
```

Note that training took **significantly** longer (a full minute!) because of the size of the base langauge model. Now, let's test our two WAV files again:

```bash
$ voice2json transcribe-wav \
    turn_on_living_room_lamp.wav | \
    jq -r .text
    
turn on the living room lamp

$ voice2json transcribe-wav \
    would_you_please_turn_on_living_room_lamp.wav | \
    jq -r .text
    
would you please turn on the living room lamp
```

Great! `voice2json` was able to transcribe a sentence that it wasn't explicitly trained on. If you're trying this at home, you surely noticed that it took a lot longer to process the WAV files too (probably 3-4x longer). In practice, it's not recommended to do mixed language modeling on lower-end hardware like a Raspberry Pi. If you need more open-ended speech recognition, try turning `voice2json` into [a network service](recipes.md#create-an-mqtt-transcription-service).

#### The Elephant in the Room

This isn't the end of the story for open-ended speech recognition in `voice2json`, however. What about *intent recognition*? When the set of possible voice commands is known ahead of time, it's relatively easy to know what to do with each and every sentence. The flexibility gained from mixing in a base language model unfortunately places a larger burden on the intent recognizer.

In our `ChangeLightState` example above, we're fortunate that everything still works as expected:

```bash
$ voice2json recognize-intent -t \
    'would you please turn on the living room lamp' | \
    jq . \
```

outputs:
    
```json
{
  "text": "turn on the living room lamp",
  "intent": {
    "name": "ChangeLightState",
    "confidence": 1
  },
  "entities": [
    {
      "entity": "state",
      "value": "on",
      "start": 5,
      "end": 7,
    }
  ],
  "tokens": [
    "turn",
    "on",
    "the",
    "living",
    "room",
    "lamp"
  ],
  "slots": {
    "state": "on"
  }
}
```

This only works because [fuzzy recognition](whitepaper.md#fuzzy-fsts) is enabled. Notice the `text` property? All the "problematic" words have simply been dropped! If you need something more sophisticated, consider [training a Rasa NLU bot](recipes.md#train-a-rasa-nlu-bot) using [generated examples](#generate-examples).

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

## recognize-intent

Recognizes an intent and slots from JSON or plaintext. Outputs a single line of [jsonl](http://jsonlines.org) for each input line ([format description](formats.md#intents)).

Inputs can be provided either as arguments **or** lines via standard in.

### JSON input

Input is a single line of [jsonl](http://jsonlines.org) per sentence, minimally with a `text` property (like the output of [transcribe-wav](#transcribe-wav)).

```bash
voice2json recognize-intent '{ "text": "turn on the light" }'
```

Output:

```json
{"text": "turn on the living room lamp", "intent": {"name": "LightState", "confidence": 1.0}, "entities": [{"entity": "state", "value": "on"}], "slots": {"state": "on"}, "recognize_seconds": 0.001}
```

### Plaintext input

Input is a single line of plaintext per sentence.

```bash
voice2json recognize-intent --text-input 'turn on the light' 'turn off the light'
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

Records from a live audio stream until a voice command has been spoken. Outputs WAV audio data containing just the voice command.

```bash
$ voice2json record-command > my-voice-command.wav
```

`record-command` uses the [webrtcvad](https://github.com/wiseman/py-webrtcvad) library to detect live speech. Once speech has been detected, `voice2json` begins recording until there is silence. If speech goes on too long, a timeout is reached and recording stops. The [profile settings](profiles.md) under the `voice-command** section control exactly how many seconds of speech and silence are needed to segement live audio.

See [audio sources](#audio-sources) for a description of how `record-command` gets audio input.

### Redirecting WAV Output

The `--wav-sink` argument lets you change where `record-command` writes its output WAV data. When this is set to something other than "-" (standard out), `record-command` will output lines of JSON to standard out that describe events in the live speech.

```bash
$ voice2json record-command \
      --audio-source <(sox turn-on-the-living-room-lamp.wav -t raw -) \
      --wav-sink /dev/null
```

will output something lile:

```json
{"event": "speech", "time_seconds": 0.24}
{"event": "started", "time_seconds": 0.54}
{"event": "silence", "time_seconds": 4.5}
{"event": "speech", "time_seconds": 4.619999999999999}
{"event": "silence", "time_seconds": 4.799999999999998}
{"event": "stopped", "time_seconds": 5.279999999999995}
```

where `event` is either "speech", "started", "silence", "stopped", or "timeout". The "started" and "stopped" events refer to the start/stop of the detected voice command. The `time_seconds` property is the time of the event relative to the start of the WAV file (time 0).

---

## pronounce-word

Uses [eSpeak](http://espeak.sourceforge.net) to pronounce words *the same way that the speech recognizer is expecting to hear them*. This depends on a manually created [phoneme map](formats.md#espeak-phoneme-maps) in each profile.

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

Generates random example sentences from [sentences.ini](sentences.md) and prompts you to record them. Saves WAV files, transcriptions, and expected intents (as [JSON events](formats.md#intents)) to a directory.

```bash
$ voice2json record-examples --directory /path/to/examples/
```

You will be prompted with a random sentence. Once you press ENTER, `voice2json` will [begin recording](#audio-sources). When you press ENTER again, the recorded audio will be saved to a WAV file in the provided `--directory` (default is the current directory). When you're finished recording examples, press CTRL+C to exit.

A directory of recorded examples can be used for [performance testing](#test-examples) or to [tune voice2json](#tune-examples) to better recognize voice commands in your acoustic environment.

---

## test-examples

Transcribes and performs intent recognition on all WAV files in a directory (usually recorded with [record-examples](#record-examples)). Outputs a JSON report with speech/intent recognition details and accuracy statistics (including [word error rate](https://en.wikipedia.org/wiki/Word_error_rate)).

```bash
$ voice2json test-examples --directory /path/to/examples/
```

outputs something like:

```json
{
  "statistics": {
    "num_wavs": 1,
    "num_words": 0,
    "num_entities": 0,
    "correct_transcriptions": 0,
    "correct_intent_names": 0,
    "correct_words": 0,
    "correct_entities": 0,
    "transcription_accuracy": 0.123,
    "intent_accuracy": 0,
    "entity_accuracy": 0
  },
  "actual": {
    "example-1.wav": {
      ...
      "word_error": {
        "expected": "...",
        "actual": "...",
        "words": 0,
        "correct": 0,
        "errors": 0
      }
    },
  },
  "expected": {
    "example-1.wav": {
    ...
  }
}

```

where `statistics` describes the overall accuracy of the examples relative to expectations, `actual` provides details of the transcription/intent recognition of the examples, and `expected` is simply pulled from the provided transcription/intent files.

### Report Format

The `statistics` section of the report contains:

* `num_wavs` - total number of WAV files that were tested
* `num_words` - total number of expected words across all test WAVs
* `num_entities` - total number of distinct entity/value pairs accross all test WAVs
* `correct_transcriptions` - number of WAV files whose actual transcriptions **exactly** matched expectations
* `correct_intent_names` - number of WAV files whose actual  intent **exactly** matched expectations
* `correct_entities` - number of entity/value pairs that **exactly** matched expectations **if and only if** the actual intent matched too
* `transcription_accuracy` - correct words / num words (1 = perfect)
* `intent_accuracy` - correct intents / num wavs (1 = perfect)
* `entity_accuracy` - correct entities / num entities (1 = perfect)

The `actual` section of the report contains the [recognized intent](formats.md#intents) of each WAV file as well as a `word_error` section with:

* `expected` - text from expected transcription (capitalized sections are incorrect)
* `actual` - text from actual transcription ('*' means missing letter)
* `words` - number of expected words
* `correct` - number of correct words
* `errors` - number of incorrect words

The `expected` section is just the intent or transcription recorded in the examples directory alongside each WAV file. For example, a WAV file named `example-1.wav` should ideally have an `example-1.json` file with an [expected intent](formats.md#intents). Failing that, an `example-1.txt` file with the transcription **must** be present.

---

## tune-examples

Tunes the speech model in your profile to your acoustic environment (speaker/microphone/room) using previously recorded examples (usually recorded with [record-examples](#record-examples)). For now, this only works if your profile is based on [pocketsphinx](https://github.com/cmusphinx/pocketsphinx).

```bash
$ voice2json tune-examples --directory /path/to/examples/
```

This will use the recorded WAV files and transcriptions to [adapt the sphinx acoustic model](https://cmusphinx.github.io/wiki/tutorialadapt/) with MLLR. When it's finished, `tune-examples` will write an [MLLR matrix](https://cmusphinx.github.io/wiki/tutorialadapt/#creating-a-transformation-with-mllr) to the file path in `speech-to-text.pocketsphinx.mllr-matrix` in your [profile](profiles.md). When `transcibe-wav` runs next, it will use this matrix during transcription.
