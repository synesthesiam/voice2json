SHELL := bash
PYTHON_FILES = voice2json/*.py

.PHONY: venv downloads check reformat docs docker-test flatpak

version := $(shell cat VERSION)
architecture := $(shell bash architecture.sh)

APP_ID='org.voice2jon.Voice2json'
FP_BUILD='.flatpak_build'
FP_REPO='repo'

all: venv

# -----------------------------------------------------------------------------

venv: downloads
	scripts/create-venv.sh

downloads:
	scripts/download-deps.sh

check:
	scripts/check-code.sh $(PYTHON_FILES)

reformat:
	scripts/format-code.sh $(PYTHON_FILES)

docs:
	scripts/build-docs.sh

# test:
# 	bash scripts/test.sh

docker-test: docs
	docker build . \
        --build-arg TARGETARCH=amd64 \
        --build-arg TARGETPLATFORM=linux/amd64 \
        --build-arg TARGETVARIANT='' \
        -t synesthesiam/voice2json:$(version)

flatpak-init:
	rm -rf $(FP_BUILD) $(FP_REPO)
	flatpak build-init $(FP_BUILD) $(APP_ID) 'org.freedesktop.Sdk' 'org.freedesktop.Platform//19.08'

flatpak-python:
	flatpak build --bind-mount=/src=$(PWD) $(FP_BUILD) /src/flatpak/01-install-python.sh

flatpak-swig:
	flatpak build --bind-mount=/src=$(PWD) $(FP_BUILD) /src/flatpak/01-install-swig.sh

flatpak-venv:
	flatpak build --bind-mount=/src=$(PWD) --share=network $(FP_BUILD) /src/flatpak/02-create-venv.sh

flatpak-voice2json:
	flatpak build --bind-mount=/src=$(PWD) $(FP_BUILD) /src/flatpak/03-install-voice2json.sh

flatpak-finish:
	flatpak build-finish $(FP_BUILD) --filesystem=xdg-config/voice2json --command=/app/voice2json.sh
	flatpak build-export $(FP_REPO) $(FP_BUILD)

flatpak-install:
	flatpak --user remote-add --no-gpg-verify --if-not-exists tutorial-repo $(FP_REPO)
	flatpak --user install tutorial-repo $(APP_ID)

flatpak-run:
	flatpak run $(APP_ID)
