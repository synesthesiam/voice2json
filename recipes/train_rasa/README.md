# Train a Rasa NLY Bot

Creates a basic [Rasa NLU assistant](https://rasa.com/docs/rasa/nlu/about/) using examples generated from `voice2json`.

## Setup

This recipes assumes you have [Docker](https://docker.com/) installed. If you don't, please follow the [Docker installation instructions](https://docs.docker.com/install/).

Once you have `voice2json` installed and a profile downloaded, copy `sentences.ini` into your profile directory (probably `$HOME/.config/voice2json`). Make sure to backup your profile first if you've done any customization!

Next, run the `train.sh` script:

```bash
$ ./train.sh
```

This script generates 5,000 random examples and converts them to Rasa NLU's [Markdown training data format](https://rasa.com/docs/rasa/nlu/training-data-format/#id5). An assistant is then trained using the [pretrained_embeddings_spacy pipeline](https://rasa.com/docs/rasa/nlu/choosing-a-pipeline/#id7).

If all goes well, you should next run the `recognize.sh` script:

```bash
$ ./recognize.sh
```

This will start a shell where you can type in sentences and see the JSON output. If you want to recognize intents remotely, you should use Rasa's [HTTP Server](https://rasa.com/docs/rasa/user-guide/running-the-server/).

```bash
$ ./rasa run -m models --enable-api
```

With that running, you can `POST` some JSON to port 5005 and get a JSON response:

```bash
$ curl -X POST -d '{ "text": "turn on the living room lamp" }' localhost:5005/model/parse
```

You can easily combine this with `voice2json`:

```bash
$ voice2json transcribe-wav \
     ../../etc/test/turn_on_living_room_lamp.wav | \
  curl -X POST -d @- localhost:5005/model/parse
```
