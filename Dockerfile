ARG BUILD_ARCH=amd64
FROM ${BUILD_ARCH}/ubuntu:bionic

ARG BUILD_ARCH=amd64
ARG DEBIAN_ARCH=${BUILD_ARCH}

COPY docker/multiarch_build/bin/qemu-* /usr/bin/

RUN apt-get update && \
    apt-get install -y \
        sox jq alsa-utils espeak sphinxtrain perl \
        python3 python3-pip \
        libatlas-base-dev libatlas3-base \
        bc

COPY debian/voice2json_1.0_${DEBIAN_ARCH}/usr/lib/voice2json/ /usr/lib/voice2json/
COPY debian/voice2json_1.0_${DEBIAN_ARCH}/usr/bin/voice2json /usr/bin/

ENTRYPOINT ["voice2json"]