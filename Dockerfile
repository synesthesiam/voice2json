ARG BUILD_ARCH=amd64
FROM ${BUILD_ARCH}/ubuntu:bionic

ARG BUILD_ARCH=amd64
ARG DEBIAN_ARCH=${BUILD_ARCH}

RUN apt-get update && \
    apt-get install -y \
        sox jq alsa-utils espeak sphinxtrain perl

COPY debian/voice2json_1.0_${DEBIAN_ARCH}.deb /root/
RUN dpkg -i /root/voice2json_1.0_${DEBIAN_ARCH}.deb

ENTRYPOINT ["voice2json"]