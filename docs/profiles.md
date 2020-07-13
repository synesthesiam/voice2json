&#8226; [Home](index.md) &#8226; Profiles

# Your Profile

A `voice2json` <strong>profile</strong> contains everything necessary to recognize voice commands, including:

* [profile.yml](#profileyml)
    * A [YAML file](https://yaml.org) with settings that override [the defaults](#default-settings)
* [sentences.ini](sentences.md)
    * A template file describing all of your voice commands
* Speech/intent models
    * `acoustic_model` - a directory with the speech model artifacts
        * [Kaldi](https://kaldi-asr.org) profiles typically have a large pre-trained `HCLG.fst` in `acoustic_model/model/graph`
        * [DeepSpeech](https://github.com/mozilla/DeepSpeech) profiles have an output graph in `model`
    * `intent.pickle.gz` - a directed graph generated during [training](commands.md#train-profile) that is converted to a [finite state transducer](http://www.openfst.org)
    * See [the whitepaper](whitepaper.md) for more details
* Pronunciation dictionaries
    * How `voice2json` expects words to be pronounced. You can [customize any word](commands.md#pronounce-word).
    * `base_dictionary.txt` - large, pre-built pronunciations for most words
    * `custom_words.txt` - small, custom pronunciation dictionary for [words that voice2json doesn't know](commands.md#unknown-words)
    * `dictionary.txt` - pronunciation dictionary generated during [training](commands.md#train-profile) containing all needed words
* Language models
    * Captures statistics about [which words follow others](whitepaper.md#language-model) in your voice commands
    * `base_language_model.txt` - large, pre-built [ARPA language model](https://cmusphinx.github.io/wiki/arpaformat/) for profile language
        * Used in [open transcription](commands.md#open-transcription) and [language model mixing](commands.md#language-model-mixing)
        * [DeepSpeech](https://github.com/mozilla/DeepSpeech)-based profiles may have an `lm.binary` file instead
        * [Julius](https://github.com/julius-speech/julius)-based profiles may have a pre-compiled `base_language_model.bin` file instead
    * `language_model.txt` - custom language model generated generated during [training](commands.md#train-profile)
* Grapheme to phoneme models
    * Used to guess how [unknown words](commands.md#unknown-words) *should* be pronounced
    * `g2p.fst` - a [finite state transducer](http://www.openfst.org) created using [phonetisaurus](https://github.com/AdolfVonKleist/Phonetisaurus)
* Phoneme Maps
    * Used to relate speech-to-text and text-to-speech [phonemes](whitepaper.md#pronunciation-dictionary)
    * `espeak_phonemes.txt` - map to [eSpeak](https://github.com/espeak-ng/espeak-ng) phonemes
    * `marytts_phonemes.txt` - map to [MaryTTS](http://mary.dfki.de/) phonemes
    * `ipa_phonemes.txt` - map to [International Phonetic Alphabet](https://en.wikipedia.org/wiki/International_Phonetic_Alphabet)

---

## profile.yml

A [YAML file](https://yaml.org) with settings that override [the defaults](#default-settings). This file typically contains the profile language's name and locale code, as well as an [eSpeak](https://github.com/espeak-ng/espeak-ng) voice to use for word pronunciations.

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
  # For deepspeech: $profile_dir/model/output_graph.pbmm
  acoustic-model: !env "${profile_dir}/acoustic_model"
  
  # Path to custom ARPA language model
  # For deepspeech: $profile_dir/lm.binary
  language-model: !env "${profile_dir}/language_model.txt"
  
  # Path to custom pronunciation dictionary
  dictionary: !env "${profile_dir}/dictionary.txt"
  
  # Pocketsphinx-specific settings
  pocketsphinx:
    # Path to tuned acoustic model matrix (pocketsphinx only)
    mllr-matrix: !env "${profile_dir}/mllr_matrix"

  # Text file with word examples for each phoneme in the pronunciation dictionary
  phoneme-examples-file: !env "${profile_dir}/phoneme_examples.txt"

  # True if acoustic model uses phonemes for pronunciations
  phoneme-pronunciations: true

  # Kaldi-specific settings
  kaldi:
    # Type of Kaldi model (either nnet3 or gmm)
    model-type: ""

    # Path to directory with custom HCLG.fst
    graph-directory: !env "${profile_dir}/acoustic_model/graph"

    # Path to directory with pre-built HCLG.fst (open transcription)
    base-graph-directory: !env "${profile_dir}/acoustic_model/model/graph"

  # Mozilla DeepSpeech-specific settings
  deepspeech:
    # Path to trie generate from sentences.ini
    trie: !env "${profile_dir}/trie"

    # Path to large, pre-built binary language model (open transcription)
    base-language-model: !env "${profile_dir}/model/lm.binary"

    # Path to large, pre-built trie (open transcription)
    base-true: !env "${profile_dir}/model/true"

# -----------------------------------------------------------------------------

intent-recognition:
  # Path to custom intent graph (stored as a gzipped networkx pickle)
  intent-graph: !env "${profile_dir}/intent.pickle.gz"
  
  # True if text should not be strictly matched
  fuzzy: true

  # Path to text file with common words to ignore (fuzzy matching only)
  stop_words: !env "${profile_dir}/stop_words.txt"

# -----------------------------------------------------------------------------

training:
  # Type of acoustic model.
  # One of: pocketsphinx, kaldi, julius, deepspeech.
  acoustic-model-type: "pocketsphinx"

  # Path to pre-built acoustic model directory
  acoustic-model: !env "${profile_dir}/acoustic_model"

  # Path to file with custom intents and sentences
  sentences-file: !env "${profile_dir}/sentences.ini"

  # Path to text file with intents that will be considered for training.
  # All intents will be considered if this file is missing.
  intent-whitelist: !env "${profile_dir}/intent_whitelist"

  # Directory containing text files, one for each $slot referenced in sentences.ini
  slots-directory: !env "${profile_dir}/slots"
  
  # Directory containing programs, one for each $slot referenced in sentences.ini
  slot-programs-directory: !env "${profile_dir}/slot_programs"
  
  # Directory containing programs, one for each !converter referenced in sentences.ini
  converters-directory: !env "${profile_dir}/converters"
  
  # Path to write custom intent finite state transducer
  intent-fst: !env "${profile_dir}/intent.fst"
  
  # Path to write custom ARPA language model
  language-model: !env "${profile_dir}/language_model.txt"
  
  # Path to write custom pronunciation dictionary
  dictionary: !env "${profile_dir}/dictionary.txt"

  # Path to extra word pronunciations outside of base dictionary
  custom-words-file: !env "${profile_dir}/custom_words.txt"

  # Action to take when multiple pronunciations for a word are available.
  # One of: "append", "overwrite_once", "overwrite_always".
  custom-words-action: "append"

  # Path to write words without any known pronunciation
  unknown-words-file: !env "${profile_dir}/unknown_words.txt"

  # Path to extra word pronunciations based on existing words instead of phonemes
  sounds-like-file: !env "${profile_dir}/sounds_like.txt"

  # Action to take when multiple pronunciations for a "sounds like" word are available.
  # One of: "append", "overwrite_once", "overwrite_always".
  sounds-like-action: "append"

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

  # Path to Phonetisaurus alignment corpus for base dictionary
  grapheme-to-phoneme-corpus: !env "${profile_dir}/g2p.corpus"

  # Force word case during dictionary lookup/g2p.
  # One of ignore, upper, lower.
  word-casing: "ignore"

  # Force word case during dictionary g2p.
  # One of default (use word-casing), upper, lower.
  g2p-word-casing: "default"

  # When true, numbers (e.g. 100) are replaced with words (one hundred).
  # This is supported for most, but not all voice2json languages.
  replace-numbers: true

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

  # Mycroft Precise settings
  precise:
      # Path to precise-engine executable.
      # Use $PATH if empty.
      engine-executable: ""

      # Path to model .pb file
      model-file: !env "${voice2json_dir}/etc/precise/hey-mycroft-2.pb"

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
  before-seconds: 0.5

  # Seconds of audio to ignore before voice command
  skip-seconds: 0.0

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
    pronounce-command: "espeak-ng -s 80 --stdout [[{phonemes}]]"

    # Command to speak sentence
    speak-command: "espeak-ng --stdout \"{sentence}\""

  marytts:
    # URL to do GET requests
    process-url: "http://localhost:59125/process"

    # Path to map between dictionary and MaryTTS phonemes
    phoneme-map: !env "${profile_dir}/marytts_phonemes.txt"

    # Token used to end a MaryTTS sentence during pronunciation.
    # I get weird pronunciations when punctuation is missing.
    sentence-end: "."

    # prosody rate used for pronunciation
    pronounce-rate: "5%"

# -----------------------------------------------------------------------------

audio:
  # Command to execute to record raw 16-bit 16Khz mono audio
  record-command: "arecord -q -r 16000 -c 1 -f S16_LE -t raw"

  # Command to convert WAV data to 16-bit 16Khz mono (stdin -> stdout)
  convert-command: "sox -t wav - -r 16000 -e signed-integer -b 16 -c 1 -t wav -"

  # Command to play a WAV file (stdin)
  play-command: "aplay -q -t wav"

  # Expected audio format.
  # Convert command is run if a different format is given.
  format:
    sample-rate-hertz: 16000
    sample-width-bits: 16
    channel-count: 1
```
