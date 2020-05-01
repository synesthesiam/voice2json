.PHONY: run debian
DOCKER_REGISTRY ?= docker.io
DOCKER_PLATFORMS ?= linux/amd64,linux/arm/v7,linux/arm64

all: run debian

run:
	docker buildx build . -f Dockerfile.run "--platform=$(DOCKER_PLATFORMS)" --tag "$(DOCKER_REGISTRY)/voice2json-run" --push

debian:
	docker buildx build . -f Dockerfile.debian "--platform=$(DOCKER_PLATFORMS)" --tag "$(DOCKER_REGISTRY)/voice2json-debian" --push
