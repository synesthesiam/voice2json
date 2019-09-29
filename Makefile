.PHONY: test installer debian docker docker-multiarch-build

BUILD_ARCH ?= amd64
DEBIAN_ARCH ?= $(BUILD_ARCH)

test:
	bash test.sh

debian: installer
	bash debianize.sh $(DEBIAN_ARCH)

installer:
	bash build.sh voice2json.spec

docker: debian
	docker build . \
        --build-arg BUILD_ARCH=$(BUILD_ARCH) \
        --build-arg DEBIAN_ARCH=$(DEBIAN_ARCH) \
        -t voice2json/voice2json:$(DEBIAN_ARCH)

# -----------------------------------------------------------------------------
# Multi-Arch Builds
# -----------------------------------------------------------------------------

docker-multiarch-build:
	docker build . -f docker/multiarch_build/Dockerfile \
        --build-arg DEBIAN_ARCH=armhf \
        --build-arg CPU_ARCH=armv7l \
        --build-arg BUILD_FROM=arm32v7/python:3.6-slim-stretch \
        -t voice2json/multi-arch-build:armhf
	docker build . -f docker/multiarch_build/Dockerfile \
        --build-arg DEBIAN_ARCH=aarch64 \
        --build-arg CPU_ARCH=arm64v8 \
        --build-arg BUILD_FROM=arm64v8/python:3.6-slim-stretch \
        -t voice2json/multi-arch-build:aarch64
