# Installing voice2json

`voice2json` has been tested on Ubuntu 18.04. It should be able to run on most any flavor of Linux using the [Docker image](#docker-image). It may even run on Mac OSX, but I don't have a Mac to test this out.

Installation options:

* [Debian Package](#debian-package)
* [Docker Image](#docker-image)
* [From Source](#from-source)

After installation:

* [Download Profile](#download-profile)

---

## Debian Package

Pre-compiled packages are available for Debian-based distributions (Ubuntu, Linux Mint, etc.) on `amd64`, `armhf`, and `aarch64` architectures. These packages are built using [PyInstaller](https://www.pyinstaller.org) and `dpkg`.

Before installing `voice2json`, you will need to install a few dependencies:

```bash
$ sudo apt-get install sox jq alsa-utils espeak-ng sphinxtrain perl
```

Next, download the appropriate `.deb` file for your CPU architecture:

* [amd64](https://github.com/synesthesiam/voice2json/releases/download/v1.0-beta/voice2json_1.0_amd64.deb) - Desktops, laptops, and servers
* [armhf](https://github.com/synesthesiam/voice2json/releases/download/v1.0-beta/voice2json_1.0_armhf.deb) - Raspberry Pi 1, 2, and 3
* [aarch64](https://github.com/synesthesiam/voice2json/releases/download/v1.0-beta/voice2json_1.0_aarch64.deb) - Raspberry Pi 3+, 4

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
$ sudo dpkg -i /path/to/voice2json_<VERSION>_<ARCH>.deb
```

where where `<VERSION>` is `voice2json`'s version (probably 1.0) and `<ARCH>` is your build architecture.

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

If you'd like to modify `voice2json`, you should clone [the repository](https://github.com/synesthesiam/voice2json) and run the [install script](https://github.com/synesthesiam/voice2json/blob/master/install.sh):

```bash
$ git clone https://github.com/synesthesiam/voice2json
$ cd voice2json
$ ./install.sh
```

Installing may take a **long time** and requires an Internet connection to download dependencies (cached in `voice2json/download`). The `install.sh` script does the following:

1. Installs required packages (assumes Debian)
2. Creates a Python virtual environment at `voice2json/.venv_<CPU_ARCH>`
    * `CPU_ARCH="$(lscpu | awk '/^Architecture/{print $2}')"`
    * Override location with `--venv <DIR>`
    * Avoid re-creating virtual environment with `--nocreate`
3. Downloads and compiles these libraries in `voice2json/build_<CPU_ARCH>`:
    * [openfst](http://www.openfst.org) - takes **forever** to compile
        * Speed up compilation with `--make-threads 8`
    * [opengrm](http://www.opengrm.org/twiki/bin/view/GRM/NGramLibrary)
    * [phonetisaurus](https://github.com/AdolfVonKleist/Phonetisaurus)
    * [Kaldi](https://kaldi-asr.org) - disable with `--nokaldi`
    * [Julius](https://github.com/julius-speech/julius) - disable with `--nojulius`
4. Installs Python dependencies into virtual environment
    * Disable with `--nopython`

If `install.sh` succeeds, you will be able to run the `voice2json.sh` script in the root of the repository in place of any `voice2json` example command.

---

## Download Profile

`voice2json` must have a [profile](profiles.md) in order to do speech/intent recognition. Because the artifacts for each language/locale can be quite large (~100MB or more), `voice2json` does not include them in its [Debian package](#debian-package), [Docker image](#docker-image), or [source repository](#from-source).

### Back Up Your Profile

If you have an existing `voice2json` profile, it is highly recommended you **regularly back up** the following files:

* `sentences.ini` - your custom voice commands
* `custom_words.txt` - your custom pronunciations
* `profile.yml` - your custom settings
* `slots` - directory with custom slot values


Profiles for each of the supported languages/locales are available for [download on Github](https://github.com/synesthesiam/voice2json-profiles). You should download the appropriate `.tar.gz` and extract it to `$HOME/.config/voice2json` (any other directory will require a `--profile` argument to be passed to `voice2json`). If everything is in the right place, `$HOME/.config/voice2json/profile.yml` will exist.

### English Example

For [English](https://github.com/synesthesiam/voice2json-profiles/tree/master/english), there are three available profiles:

1. [en-us_pocketsphinx-cmu](https://github.com/synesthesiam/en-us_pocketsphinx-cmu)
2. [en-us_kaldi-zamia](https://github.com/synesthesiam/en-us_kaldi-zamia)
3. [en-in_pocketsphinx-cmu](https://github.com/synesthesiam/en-in_pocketsphinx-cmu)

The first two profiles are for U.S. English (`en-us`), while the third is for Indian English (`en-in`). For U.S. English, you will probably want to start with the [en-us_pocketsphinx-cmu](https://github.com/synesthesiam/en-us_pocketsphinx-cmu) profile, which is based on [pocketsphinx](https://github.com/cmusphinx/pocketsphinx). This profile provides good accuracy and is typically faster than [en-us_kaldi-zamia](https://github.com/synesthesiam/en-us_kaldi-zamia), though the latter tends to be more accurate, *especially* with [open transcription](commands.md#open-transcription).

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
```

