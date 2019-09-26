# voice2json

`voice2json` is a set of command-line tools for offline, multilingual speech/intent recognition.

## Commands

* `print-profile`
    * Print profile JSON to console
* `train-profile`
    * Create custom speech/intent recognizer from `sentences.ini`
* `transcribe-wav`
    * Transcribe WAV file to text
* `recognize-intent`
    * Recognize intent from JSON or text
* `wait-wake`
    * Listen to live audio stream until wake word is spoken
* `record-command`
    * Record voice command from live audio stream
* `pronounce-word`
    * Look up or guess how a word is pronounced
* `generate-examples`
    * Generate random intents
* `record-examples`
    * Record speech examples of random intents to a directory
* `test-examples`
    * Transcribe and recognize recorded speech examples for performance testing
* `tune-examples`
    * Tune acoustic model to better recognize recorded speech examples

## Profile

If `--profile` is not given, a profile is expected at `$XDG_CONFIG_HOME/voice2json`, which is usually `$HOME/.config/voice2json`.

A YAML file named `profile.yml` must exist in this directory with settings for `voice2json`. Within `profile.yml`, the `!env` constructor can be used to expand environment variables. `voice2json` will automatically set the following environment variables:

* `voice2json_dir` - directory where `voice2json` is installed
* `profile_dir` - directory where `profile.yml` was loaded from
* `machine` - value of Python's `platform.machine()`
    * Usually `x86_64`, `armv7l`, `armv6l`, etc.

Default settings for `profile.yml` are in [profile.defaults.yml](etc/profile.defaults.yml).
