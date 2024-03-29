&#8226; [Home](index.md) &#8226; Install

# Installing voice2json

`voice2json` has been tested on Ubuntu 18.04. It should be able to run on most any flavor of Linux using the [Docker image](#docker-image). It may even run on Mac OSX, but I don't have a Mac to test this out.

Installation options:

* [Debian Package](#debian-package)
* [Docker Image](#docker-image)
* [From Source](#from-source)

After installation:

* [Download Profile](#download-profile)

---

## Supported Hardware

`voice2json` is supported on typical desktops/laptops as well as the Raspberry Pi, including the Pi Zero (`armel`).

| Category           | Name                                                            | amd64    | armv7    | arm64    |
| --------           | ------                                                          | -------  | -------  | -------  |
| **Wake Word**      | [Mycroft Precise](https://github.com/MycroftAI/mycroft-precise) | &#x2713; | &#x2713; | &#x2713; |
| **Speech to Text** | [Pocketsphinx](https://github.com/cmusphinx/pocketsphinx)       | &#x2713; | &#x2713; | &#x2713; |
|                    | [Kaldi](https://kaldi-asr.org)                                  | &#x2713; | &#x2713; | &#x2713; |
|                    | [DeepSpeech](https://github.com/mozilla/DeepSpeech)             | &#x2713; | &#x2713; |          |
|                    | [Julius](https://github.com/julius-speech/julius)               | &#x2713; | &#x2713; | &#x2713; |

---

## Debian Package

Pre-compiled packages are available for Debian-based distributions (Ubuntu, Linux Mint, etc.) on `amd64`, `armhf`, and `arm64` (`aarch64`) architectures. These packages are built using Docker and `dpkg`.

Next, download the appropriate `.deb` file for your CPU architecture:

* [amd64](https://github.com/synesthesiam/voice2json/releases/download/v2.1/voice2json_2.1_amd64.deb) - Desktops, laptops, and servers
* [armhf](https://github.com/synesthesiam/voice2json/releases/download/v2.1/voice2json_2.1_armhf.deb) - Raspberry Pi 2, and 3/3+ (armv7)
* [arm64](https://github.com/synesthesiam/voice2json/releases/download/v2.1/voice2json_2.1_arm64.deb) - Raspberry Pi 3+, 4

If you're unsure about your architecture, run:

```bash
$ dpkg-architecture | grep DEB_BUILD_ARCH=
```

which will output something like:

```bash
DEB_BUILD_ARCH=amd64
```

Next, install the `.deb` file:

```bash
$ sudo apt install /path/to/voice2json_<VERSION>_<ARCH>.deb
```

where where `<VERSION>` is `voice2json`'s version (probably 2.1) and `<ARCH>` is your build architecture.

**NOTE**: If you run `sudo apt install` in the same directory as the `.deb` file, make sure to prefix the filename with `./` like this:

```bash
$ sudo apt install ./voice2json_<VERSION>_<ARCH>.deb
```

After [downloading a profile](commands.md#download-profile), you should now be able to run any of the example `voice2json` commands in the documentation.

---

## Docker Image

The easiest way to try out `voice2json` is with [Docker](https://docker.com). Pre-built images are available for `amd64`, `armhf`, `armel`, and `arm64` (`aarch64`) CPU architectures. To get started, make sure you have [Docker installed](https://docs.docker.com/install/):

```bash
$ curl -sSL https://get.docker.com | sh
```
    
and that your user is part of the `docker` group:

```bash
$ sudo usermod -a -G docker $USER
```
    
**Be sure to reboot** after adding yourself to the `docker` group!

### Shell Script

Create a Bash script named `voice2json` somewhere in your `$PATH` and add the following content ([source](https://github.com/synesthesiam/voice2json/blob/master/docker/voice2json)):

```bash
#!/usr/bin/env bash
docker run -i \
       --init \
       -v "${HOME}:${HOME}" \
       -v "/dev/shm/:/dev/shm/" \
       -w "$(pwd)" \
       -e "HOME=${HOME}" \
       --user "$(id -u):$(id -g)" \
       synesthesiam/voice2json "$@"
```

Mark it as executable with `chmod +x /path/to/voice2json` and try it out:

```bash
$ voice2json --help
```

After [downloading a profile](commands.md#download-profile), you should now be able to run any of the example `voice2json` commands in the documentation.

### Microphone Access

Getting Docker to properly use your microphone [can be difficult](https://github.com/synesthesiam/voice2json/issues/21). For commands like `transcribe-stream` that operate on a live audio stream, try:

1. Adding `--device /dev/snd:/dev/snd` to your `docker run` command, or
2. Piping audio in with something like `arecord -r 16000 -f S16_LE -c 1 | voice2json transcribe-stream --audio-source -`

### Updating

To update your `voice2json` Docker image, simply run:

```bash
$ docker pull synesthesiam/voice2json
```

---

## From Source

`voice2json` uses [autoconf](https://www.gnu.org/software/autoconf/) to facilitate building from source. You will need Python 3.7 and some common build tools like `gcc`.

Once you've cloned the [the repository](https://github.com/synesthesiam/voice2json), the build steps should be familiar:

```bash
$ git clone https://github.com/synesthesiam/voice2json
$ cd voice2json
$ ./configure
$ make
$ make install
```

This will install `voice2json` inside a virtual environment at `$PWD/.venv` by default with **all** of the supported speech to text engines and supporting tools. When installation is finished, copy `voice2json.sh` somewhere in your `PATH` and rename it to `voice2json`.

If you are building from source on macOS, you will also need to install [coreutils](https://www.gnu.org/software/coreutils/):

```bash
$ brew install coreutils
```

### Customizing Installation

You can pass additional information to `configure` to avoid installing parts of `voice2json` that you won't use. For example, if you only plan to use the French language profiles, set the `VOICE2JSON_LANGUAGE` environment variable to `fr` when configuring your installation:

```bash
$ ./configure VOICE2JSON_LANGUAGE=fr
```

The installation will now be configured to install only Kaldi (if supported). If instead you want a specific speech to text system, use `VOICE2JSON_SPEECH_SYSTEM` like:

```bash
$ ./configure VOICE2JSON_SPEECH_SYSTEM=deepspeech
```

which will only enable DeepSpeech.

To force the supporting tools to be built from source instead of downloading pre-compiled binaries, use `--disable-precompiled-binaries`. Dependencies will be compiled in a `build` directory (override with `$BUILD_DIR` during `make`), and bundled for installation in `download` (override with `$DOWNLOAD_DIR`).

See `./configure --help` for additional options.

---

## Download Profile

`voice2json` must have a [profile](profiles.md) in order to do speech/intent recognition. Because the artifacts for each language/locale can be quite large (100's of MB or more), `voice2json` does not include them in its [Debian package](#debian-package), [Docker image](#docker-image), or [source repository](#from-source).

To download artifacts for a specific profile or language, use:

```bash
$ voice2json --debug --profile <PROFILE> download-profile
```

where `<PROFILE>` is one of the [supported languages](index.md#supported-languages) (like `en` or `fr`), or one of the [known profile names](https://github.com/synesthesiam/voice2json/tree/master/etc/profiles) like `de_kaldi-zamia`.

**Note**: The post-download process may take a long time, especially on Raspberry Pi (SD card). This is because `voice2json` is decompressing and re-combining split files from [GitHub](https://github.com/synesthesiam/voice2json-profiles).


Once everything is downloaded (by default in `$HOME/.local/share/voice2json`), you should be able to train your profile:

```bash
$ voice2json --debug --profile <PROFILE> train-profile
```

If you manually download or move files to the `$HOME/.config/voice2json` directory, you may omit the `--profile` argument to `voice2json`.

### Test Your Profile

Once you've trained your profile, you can quickly test it out with:

```bash
$ voice2json --profile <PROFILE> transcribe-stream
```

The [`transcribe-stream`](commands.md#transcribe-stream) will record from your microphone (using `arecord` and the default device), wait for you to speak a voice command, and then output a transcription (hit CTRL + C to exit).

If you're using the default English sentences, try saying "turn on the living room lamp" and wait for the output. Getting intents out is as easy as:

```bash
$ voice2json --profile <PROFILE> transcribe-stream | \
    voice2json --profile <PROFILE> recognize-intent
```

Speaking a voice command should now output a line of JSON with the recognized intent. For example, "what time is it" outputs something like:

```json
{
  "text": "what time is it",
  "likelihood": 0.025608657540496446,
  "transcribe_seconds": 1.4270143630001257,
  "wav_seconds": 0.0043125,
  "tokens": [
    "what",
    "time",
    "is",
    "it"
  ],
  "timeout": false,
  "intent": {
    "name": "GetTime",
    "confidence": 1
  },
  "entities": [],
  "raw_text": "what time is it",
  "recognize_seconds": 0.00019677899945236277,
  "raw_tokens": [
    "what",
    "time",
    "is",
    "it"
  ],
  "speech_confidence": null,
  "wav_name": null,
  "slots": {}
}
```

### Back Up Your Profile

If you have an existing `voice2json` profile, it is highly recommended you **regularly back up** the following files:

* `sentences.ini` - your custom voice commands
* `custom_words.txt` - your custom pronunciations
* `profile.yml` - your custom settings
* `slots` - directory with custom slot values
* `slot_programs` - directory with custom slot programs
* `converters` - directory with custom conversion programs

See the [`print-files`](commands.md#print-files) for an easy way to automate backups.
