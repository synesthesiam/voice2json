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
$ voice2json print-profile
```

Output:

```json
{
    "language": {
        "name": "english",
        "code": "en-us"
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

### WAV file(s) as arguments

Reads one or more WAV files and transcribes each of them in turn.

```bash
$ voice2json transcribe-wav turn-on-the-light.wav what-time-is-it.wav
```

Output:


```json
{"text": "turn on the light", "transcribe_seconds": 0.123, "wav_seconds": 1.456, "wav_name": "turn-on-the-light.wav"}
{"text": "what time is it", "transcribe_seconds": 0.123, "wav_seconds": 1.456, "wav_name": "what-time-is-it.wav"}
```

### WAV file(s) from stdin

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

Listens to a live audio stream until the wake word is spoken.

---

## record-command

Records from a live audio stream until a voice command has been spoken.

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

In addition to text output, you should have heard both pronunciations of "hello". These came the `base_dictionary.txt` included in the profile. The same command works for words that are definitely **not** in the U.S. English dictionary:

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
  }
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

---

## record-examples

---

## test-examples

---

## tune-examples

Pocketsphinx only.
