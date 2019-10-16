# Fluent Speech Dataset

Demonstration of `voice2json`'s performance on a [public dataset from Fluent.ai](http://www.fluent.ai/research/fluent-speech-commands/).

## Results

Using ~100 lines in [sentences.ini](sentences.ini) (excluding comments), I'm able to get 98.7% accuracy, which is as accurate as the end-to-end system trained in [Fluent.ai's published paper](https://arxiv.org/pdf/1904.03670.pdf)! While the sentences `voice2json` was trained with had to be hand-tuned to fit the test sets, it also did not require any audio data for training.

## Running

Before getting started, make sure you have [GNU Parallel](http://www.gnu.org/s/parallel) and [jq](https://stedolan.github.io/jq/) installed:

```bash
$ sudo apt-get install parallel jq
```

To reproduce the results, extract the [U.S. English Kaldi profile](https://github.com/synesthesiam/en-us_kaldi-zamia) to `$HOME/.config/voice2json`. Copy the `sentences.ini` from here to `$HOME/.config/voice2json/sentences.ini` and train the profile:

```bash
$ voice2json train-profile
```

Next, [download the dataset](http://www.fluent.ai/research/fluent-speech-commands/) and extract the `wavs` directory here.

Finally, run `make` in this directory:

```bash
$ make
```

By default, this will run 10 parallel transcription/intent recognition processes and generate `results/report.json`. The top of mine looks like this:

```json
  "statistics": {
    "num_wavs": 3793,
    "num_words": 16523,
    "num_entities": 8140,
    "correct_transcriptions": 3157,
    "correct_intent_names": 3781,
    "correct_words": 15731,
    "correct_entities": 8079,
    "transcription_accuracy": 0.9520668159535194,
    "intent_accuracy": 0.9968362773530187,
    "entity_accuracy": 0.9925061425061426,
    "intent_entity_accuracy": 0.9870814658581598,
    "average_transcription_speedup": 1.8713219495029716
  },
  ...
}
```

The `intent_entity_accuracy` metric is the number of examples where the recognized intent and entities matched **exactly** divided by the total number of examples. Note that this is actually higher than the transcription accuracy (95.2%); `voice2json` can recover from some transcription errors during intent recognition.
