# DeepSpeech Transcriber for voice2json

Demonstrates using artifacts from a `voice2json` profile to "train" a [Mozilla DeepSpeech](https://github.com/mozilla/DeepSpeech) model.

## Model

The `output_graph.pb` file from the [pre-trained model](https://github.com/mozilla/DeepSpeech#getting-the-pretrained-model) should go in the `model` directory.

## Building and Running

After training your profile, run `make` in the `recipes/deepspeech` directory. You should now be able to run `deep_transcribe.py` (from the same directory) with 16-bit 16Khz mono on standard in:

```bash
$ sox some-wav-file.wav -r 16000 -e signed-integer -c 1 -t raw - | \
      ./deep_transcribe.py
```

## Requirements

The `bin` directory includes pre-compiled binaries for `x86_64` machines. If you're running on a different architecture, you'll need to compile [kenlm](https://kheafield.com/code/kelm) and copy the `build_binary` program to `bin`. On a Debian system, that requires the following packages:

* libboost-program-options-dev
* libboost-system-developer
* libboost-thread-dev
* libboost-test-dev
* libeigen3-dev
* libbz2-dev

You will also need an appropriate version of `generate_trie` which comes from [the native client](https://github.com/mozilla/DeepSpeech/blob/master/native_client/README.md). It should go in `bin` too.
