# Profiles

A `voice2json` <strong>profile</strong> contains everything necessary to recognize voice commands, including:

* [profile.yml](#profileyml)
    * A [YAML file](https://yaml.org) with settings that override [the defaults](#default-settings)
* [sentences.ini](sentences.md)
    * A template file describing all of your voice commands
* Speech/intent models
    * `acoustic_model` - a directory with the speech model
    * `intent.fst` - a [finite state transducer](http://www.openfst.org) generated during [training](commands.md#traing-profile)
    * See [the whitepaper](whitepaper.md) for more details
* Pronunciation dictionaries
    * How `voice2json` expects words to be pronounced. You can [customize any word](commands.md#pronounce-word).
    * `base_dictionary.txt` - large, pre-built pronunciations for most words
    * `custom_words.txt` - small, custom pronunciations for your words
* Grapheme to phoneme models
    * Used to guess how [unknown words](commands.md#unknown-words) *should* be pronounced.
    * `g2p.fst` - a [finite state transducer](http://www.openfst.org) created using [phonetisaurus](https://github.com/AdolfVonKleist/Phonetisaurus)

---

## profile.yml

A [YAML file](https://yaml.org) with settings that override [the defaults](#default-settings). This file typically contains the profile language's name and locale code, as well as an [eSpeak](http://espeak.sourceforge.net) voice to use for word pronunciations.

For Kaldi-based profiles, `kaldi.model-type` **must** be set to either `gmm` or `nnet3`.

### Environment Variables

You can use the `!env` constructor in your `profile.yml` file to expand environment variables inside string values.

`voice2json` makes the following environment variables are available when profiles are loaded:

* `profile_dir` - directory where `profile.yml` was loaded from
* `voice2json_dir` - directory where `voice2json` is installed
* `machine` - CPU architecture as reported by Python's `platform.machine()`
    * Typically `x86_64`, `armv7l`, `armv6l`, etc.
    
---

## Default Settings

The default values for all profile settings are stored in `etc/profile.defaults.yml`.

```yaml
speech-to-text:
  # Path to pre-built acoustic model directory
  acoustic-model: !env "${profile_dir}/acoustic_model"
  
  # Path to custom ARPA language model
  language-model: !env "${profile_dir}/language_model.txt"
  
  # Path to custom pronunciation dictionary
  dictionary: !env "${profile_dir}/dictionary.txt"
  
  # Pocketsphinx-specific settings
  pocketsphinx:
    # Path to tuned acoustic model matrix (pocketsphinx only)
    mllr-matrix: !env "${profile_dir}/mllr_matrix"

  # Kaldi-specific settings
  kaldi:
    # Type of Kaldi model (either nnet3 or gmm)
    model-type: ""

    # Path to directory with custom HCLG.fst
    graph-directory: !env "${profile_dir}/acoustic_model/graph"

    # Path to directory with pre-built HCLG.fst (open transcription)
    base-graph-directory: !env "${profile_dir}/acoustic_model/model/graph"

# -----------------------------------------------------------------------------

intent-recognition:
  # Path to custom intent finite state transducer
  intent-fst: !env "${profile_dir}/intent.fst"
  
  # True if words outside of sentences.ini should be ignored
  skip-unknown: true
  
  # True if text should not be strictly matched
  fuzzy: true

  # Path to text file with common words to ignore (fuzzy matching only)
  stop_words: !env "${profile_dir}/stop_words.txt"

# -----------------------------------------------------------------------------

training:
  # Path to file with custom intents and sentences
  sentences-file: !env "${profile_dir}/sentences.ini"
  
  # Path to text file with intents that will be considered for training.
  # All intents will be considered if this file is missing.
  intent_whitelist: !env "${profile_dir}/intent_whitelist"

  # Directory containing text files, one for each $slot referenced in sentences.ini
  slots-directory: !env "${profile_dir}/slots"

  # Path to write custom intent finite state transducer
  intent-fst: !env "${profile_dir}/intent.fst"
  
  # Path to write custom ARPA language model
  language-model: !env "${profile_dir}/language_model.txt"
  
  # Path to write custom pronunciation dictionary
  dictionary: !env "${profile_dir}/dictionary.txt"

  # Path to extra word pronunciations outside of base dictionary
  custom-words-file: !env "${profile_dir}/custom_words.txt"

  # Path to write words without any known pronunciation
  unknown-words-file: !env "${profile_dir}/unknown_words.txt"

  # Path to pre-built ARPA language model (open transcription)
  base-language-model: !env "${profile_dir}/base_language_model.txt"
  
  # Path to save compiled finite state transducer for base language model
  base-language-model-fst: !env "${profile_dir}/base_language_model.fst"

  # Amount of base language model to mix into custom language model
  base-language-model-weight: 0.0

  # Path to pre-built pronunciation dictionary
  base-dictionary: !env "${profile_dir}/base_dictionary.txt"
  
  # Path to model used to guess unknown word pronunciation
  grapheme-to-phoneme-model: !env "${profile_dir}/g2p.fst"

  # Kaldi-specific settings
  kaldi:
    # Type of Kaldi model (either nnet3 or gmm)
    model-type: ""

    # Path to directory where custom HCLG.fst will be written
    graph-directory: !env "${profile_dir}/acoustic_model/graph"

# -----------------------------------------------------------------------------

wake-word:
  # Sensitivity (0-1)
  sensitivity: 0.5

  # Porcupine-specific settings
  porcupine:
      # Path to porcupine shared object library
      library-file: !env "${voice2json_dir}/etc/porcupine/lib/${machine}/libpv_porcupine.so"

      # Path to porcupine params file
      params-file: !env "${voice2json_dir}/etc/porcupine/lib/common/porcupine_params.pv"

      # Path to procupine keyword file
      keyword-file: !env "${voice2json_dir}/etc/porcupine/keyword_files/porcupine_${machine}.ppn"
  
# -----------------------------------------------------------------------------

voice-command:
  # Minimum number of seconds a voice command must last (ignored otherwise)
  minimum-seconds: 2

  # Maximum number of seconds a voice command can last (timeout otherwise)
  maximum-seconds: 30

  # Seconds of speech detected before voice command is considered started
  speech-seconds: 0.3

  # Seconds of silence before voice command is considered ended
  silence-seconds: 0.5

  # Seconds of audio before voice command starts to retain in output
  before-seconds: 0.25

  # webrtcvad specific settings
  webrtcvad:
    # Speech filtering aggressiveness 0-3 (3 is most aggressive) 
    vad-mode: 3

# -----------------------------------------------------------------------------

text-to-speech:
  # espeak specific settings
  espeak:
    # Path to map between dictionary and espeak phonemes
    phoneme-map: !env "${profile_dir}/espeak_phonemes.txt"

    # Command to execute to pronounce some espeak phonemes
    pronounce-command: "espeak -s 80 [[{phonemes}]]"

# -----------------------------------------------------------------------------

audio:
  # Command to execute to record raw 16-bit 16Khz mono audio
  record-command: "arecord -q -r 16000 -c 1 -f S16_LE -t raw"

  # Command to convert WAV data to 16-bit 16Khz mono (stdin -> stdout)
  convert-command: "sox -t wav - -r 16000 -e signed-integer -b 16 -c 1 -t wav -"
```
