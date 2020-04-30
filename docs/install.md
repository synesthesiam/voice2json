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

| Category           | Name                                                            | amd64    | armv7    | arm64    |
| --------           | ------                                                          | -------  | -------  | -------  |
| **Wake Word**      | [Mycroft Precise](https://github.com/MycroftAI/mycroft-precise) | &#x2713; | &#x2713; | &#x2713; |
| **Speech to Text** | [Pocketsphinx](https://github.com/cmusphinx/pocketsphinx)       | &#x2713; | &#x2713; | &#x2713; |
|                    | [Kaldi](https://kaldi-asr.org)                                  | &#x2713; | &#x2713; | &#x2713; |
|                    | [DeepSpeech](https://github.com/mozilla/DeepSpeech)             | &#x2713; | &#x2713; |          |

---

## Debian Package

Pre-compiled packages are available for Debian-based distributions (Ubuntu, Linux Mint, etc.) on `amd64`, `armhf`, and `aarch64` architectures. These packages are built using Docker and `dpkg`.

Next, download the appropriate `.deb` file for your CPU architecture:

* [amd64](https://github.com/synesthesiam/voice2json/releases/download/v1.0-beta/voice2json_1.0_amd64.deb) - Desktops, laptops, and servers
* [armhf](https://github.com/synesthesiam/voice2json/releases/download/v1.0-beta/voice2json_1.0_armhf.deb) - Raspberry Pi 1, 2, and 3 (armv7)
* [aarch64](https://github.com/synesthesiam/voice2json/releases/download/v1.0-beta/voice2json_1.0_aarch64.deb) - Raspberry Pi 3+, 4 (arm64)

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

where where `<VERSION>` is `voice2json`'s version (probably 2.0) and `<ARCH>` is your build architecture.

After [downloading a profile](#download-profile), you should now be able to run any of the example `voice2json` commands in the documentation.

---

## Docker Image

The easiest way to try out `voice2json` is with [Docker](https://docker.com). Pre-built images are available for `amd64`, `armhf`, and `aarch64` CPU architectures. To get started, make sure you have [Docker installed](https://docs.docker.com/install/):

```bash
$ curl -sSL https://get.docker.com | sh
```
    
and that your user is part of the `docker` group:

```bash
$ sudo usermod -a -G docker $USER
```
    
**Be sure to reboot** after adding yourself to the `docker` group!

### Shell Script

Create a Bash script named `voice2json` somewhere in your `$PATH` and add the following content:

```bash
#!/usr/bin/env bash
docker run -i \
       -v "${HOME}:${HOME}" \
       -w "$(pwd)" \
       -e "HOME=${HOME}" \
       --user "$(id -u):$(id -g)" \
       synesthesiam/voice2json "$@"
```

Mark it as executable with `chmod +x /path/to/voice2json` and try it out:

```bash
$ voice2json --help
```

After [downloading a profile](#download-profile), you should now be able to run any of the example `voice2json` commands in the documentation.

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

`voice2json` must have a [profile](profiles.md) in order to do speech/intent recognition. Because the artifacts for each language/locale can be quite large (~100MB or more), `voice2json` does not include them in its [Debian package](#debian-package), [Docker image](#docker-image), or [source repository](#from-source).

### Back Up Your Profile

If you have an existing `voice2json` profile, it is highly recommended you **regularly back up** the following files:

* `sentences.ini` - your custom voice commands
* `custom_words.txt` - your custom pronunciations
* `profile.yml` - your custom settings
* `slots` - directory with custom slot values
* `slot_programs` - directory with custom slot programs
* `converters` - directory with custom conversion programs

Profiles for each of the supported languages/locales are available for [download on Github](https://github.com/synesthesiam/voice2json-profiles). You should download the appropriate `.tar.gz` and extract it to `$HOME/.config/voice2json` (any other directory will require a `--profile` argument to be passed to `voice2json`). If everything is in the right place, `$HOME/.config/voice2json/profile.yml` will exist.

### English Example

For [English](https://github.com/synesthesiam/voice2json-profiles/tree/master/english), there are five available profiles:

1. [en-us_pocketsphinx-cmu](https://github.com/synesthesiam/en-us_pocketsphinx-cmu)
2. [en-us_kaldi-zamia](https://github.com/synesthesiam/en-us_kaldi-zamia)
3. [en-us_deepspeech-mozilla](https://github.com/synesthesiam/en-us_deepspeech-mozilla)
4. [en-us_julius-github](https://github.com/synesthesiam/en-us_julius-github)
5. [en-in_pocketsphinx-cmu](https://github.com/synesthesiam/en-in_pocketsphinx-cmu)

The first four profiles are for U.S. English (`en-us`), while the third is for Indian English (`en-in`). For U.S. English, you will probably want to start with the [en-us_pocketsphinx-cmu](https://github.com/synesthesiam/en-us_pocketsphinx-cmu) profile, which is based on [pocketsphinx](https://github.com/cmusphinx/pocketsphinx). This profile provides a good balance of accuracy and speed. For [open transcription](commands.md#open-transcription), however [en-us_kaldi-zamia](https://github.com/synesthesiam/en-us_kaldi-zamia) and [en-us_deepspeech-mozilla](https://github.com/synesthesiam/en-us_deepspeech-mozilla) are much better options.

Downloading and installing the [en-us_pocketsphinx-cmu](https://github.com/synesthesiam/en-us_pocketsphinx-cmu) is straightforward from the command-line:

```bash
$ mkdir -p "${HOME}/.config/voice2json"
$ curl -SL \
      https://github.com/synesthesiam/en-us_pocketsphinx-cmu/archive/v1.0.tar.gz | \
      tar -C "${HOME}/.config/voice2json" --skip-old-files --strip-components=1 -xzvf -
```

**Note**: The `--skip-old-files` argument to `tar` will ensure that your `sentences.ini` and `custom_words.txt` files are not overwritten. Remove this argument to completely overwrite your profile.

Now you should be able to train your profile:

```bash
$ voice2json train-profile
```

If you extracted the profile files to a directory other than `$HOME/.config/voice2json`, you will need to pass a `--profile` argument to `voice2json`:

```bash
$ voice2json --profile /path/to/profile/files/ train-profile
``

**Note**: The first time you train your profile may take a long time, especially on Raspberry Pi (SD card). This is because `voice2json` is decompressing and re-combining split files from GitHub.
