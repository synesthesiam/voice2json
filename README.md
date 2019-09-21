# voice2json

## Commands

* `train-profile`
* `generate-examples`
* `transcribe-wav`
* `recognize-text`
* `wait-wake`
* `record-command`
* `pronounce-word`
* `record-examples`
* `test-examples`
* `tune-examples`

## Profile

If `--profile` is not given, a profile is expected at `$XDG_CONFIG_HOME/voice2json`, which is usually `$HOME/.config/voice2json`.

A YAML file named `profile.yml` must exist in this directory with settings for `voice2json`. Within `profile.yml`, the `!env` constructor can be used to expand environment variables. `voice2json` will automatically set the `profile_dir` environment variable to be the directory where `profile.yml` was loaded from.

Available settings for `profile.yml` are:

```yaml
speech-to-text:
  # Path to pre-built acoustic model directory
  acoustic-model: !env "${profile_dir}/acoustic_model"
  
  # Path to custom ARPA language model
  language-model: !env "${profile_dir}/language_model.txt"
  
  # Path to custom pronunciation dictionary
  dictionary: !env "${profile_dir}/dictionary.txt"
  
  # Path to tuned acoustic model matrix (pocketsphinx only)
  mllr-matrix: !env "${profile_dir}/mllr_matrix"

intent-recognition:
  # Path to custom intent finite state transducer
  intent-fst: !env "${profile_dir}/intent.fst"
  
  # True if words outside of sentences.ini should be ignored
  skip-unknown: true
  
  # True if text should not be strictly matched
  fuzzy: true

  # Path to text file with common words to ignore (fuzzy matching only)
  stop_words: !env "${profile_dir}/stop_words.txt"

training:
  # Path to file with custom intents and sentences
  sentences-file: !env "${profile_dir}/sentences.ini"
  
  # Path to write custom intent finite state transducer
  intent-fst: !env "${profile_dir}/intent.fst"
  
  # Path to write custom ARPA language model
  language-model: !env "${profile_dir}/language_model.txt"
  
  # Path to write custom pronunciation dictionary
  dictionary: !env "${profile_dir}/dictionary.txt"

  # Path to extra word pronunciations outside of base dictionary
  custom-words-file: !env "${profile_dir}/unknown_words.txt"

  # Path to write words without any known pronunciation
  unknown-words-file: !env "${profile_dir}/unknown_words.txt"

  # Path to pre-built ARPA language model (open transcription)
  base-language-model: !env "${profile_dir}/base_language_model.txt"
  
  # Path to pre-built pronunciation dictionary
  base-dictionary: !env "${profile_dir}/base_dictionary.txt"
  
  # Path to model used to guess unknown word pronunciation
  grapheme-to-phoneme-model: !env "${profile_dir}/g2p.fst"

wake-word:
  # Path to porcupine shared object library
  library-file: !env "${profile_dir}/porcupine/lib/${machine}/libpv_porcupine.so"
  
  # Path to porcupine params file
  params-file: !env "${profile_dir}/porcupine/lib/common/porcupine_params.pv"
  
  # Path to procupine keyword file
  keyword-file: !env "${profile_dir}/porcupine/keyword_files/porcupine_${machine}.ppn"
  
  # Sensitivity (0-1)
  sensitivity: 0.5
  
text-to-speech:
  # Path to map between dictionary and espeak phonemes
  phoneme-map: !env "${profile_dir}/espeak_phonemes.txt"
```
