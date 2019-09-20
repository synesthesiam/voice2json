.PHONY: installer debian docker

FRIENDLY_ARCH ?= amd64

debian: installer
	bash debianize.sh $(FRIENDLY_ARCH)

installer:
	bash build.sh voice2json.spec

docker: debian
	docker build . \
        --build-arg BUILD_ARCH=$(FRIENDLY_ARCH) \
        -t voice2json/voice2json
