.PHONY: test installer debian docker docker-multiarch-build

BUILD_ARCH ?= amd64
DEBIAN_ARCH ?= $(BUILD_ARCH)

test:
	bash test.sh

debian: installer
	bash debianize.sh --architecture $(DEBIAN_ARCH)

installer:
	bash build.sh voice2json.spec

docker: installer
	bash debianize.sh --nopackage --architecture $(DEBIAN_ARCH)
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
        --build-arg BUILD_FROM=arm32v7/ubuntu:bionic \
        -t voice2json/multi-arch-build:armhf
	# docker build . -f docker/multiarch_build/Dockerfile \
  #       --build-arg DEBIAN_ARCH=aarch64 \
  #       --build-arg CPU_ARCH=arm64v8 \
  #       --build-arg BUILD_FROM=arm64v8/ubuntu:bionic \
  #       -t voice2json/multi-arch-build:aarch64

docker-multiarch-install: docker-multiarch-build
	docker run -it \
      -v "$$(pwd):$$(pwd)" -w "$$(pwd)" \
      -e DEBIAN_ARCH=armhf \
      voice2json/multi-arch-build:armhf \
      install.sh --noruntime
	docker run -it \
      -v "$$(pwd):$$(pwd)" -w "$$(pwd)" \
      -e DEBIAN_ARCH=aarch64 \
      voice2json/multi-arch-build:aarch64 \
      install.sh --noruntime

docker-multiarch-debian: docker-multiarch-build
	docker run -it \
      -v "$$(pwd):$$(pwd)" -w "$$(pwd)" \
      -e DEBIAN_ARCH=armhf \
      voice2json/multi-arch-build:armhf \
      make multiarch-debian
	docker run -it \
      -v "$$(pwd):$$(pwd)" -w "$$(pwd)" \
      -e DEBIAN_ARCH=aarch64 \
      voice2json/multi-arch-build:aarch64 \
      make multiarch-debian

multiarch-debian:
	bash build.sh --novenv voice2json.spec
	bash debianize.sh --architecture $(DEBIAN_ARCH)
