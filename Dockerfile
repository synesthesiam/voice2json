FROM ubuntu:eoan as build-amd64

ENV LANG C.UTF-8

RUN apt-get update && \
    apt-get install --no-install-recommends --yes \
        python3 python3-dev python3-setuptools python3-pip python3-venv \
        build-essential swig libatlas-base-dev portaudio19-dev

# -----------------------------------------------------------------------------

FROM ubuntu:eoan as build-armv7

ENV LANG C.UTF-8

RUN apt-get update && \
    apt-get install --no-install-recommends --yes \
        python3 python3-dev python3-setuptools python3-pip python3-venv \
        build-essential swig libatlas-base-dev portaudio19-dev

# -----------------------------------------------------------------------------

FROM ubuntu:eoan as build-arm64

ENV LANG C.UTF-8

RUN apt-get update && \
    apt-get install --no-install-recommends --yes \
        python3 python3-dev python3-setuptools python3-pip python3-venv \
        build-essential swig libatlas-base-dev portaudio19-dev

# -----------------------------------------------------------------------------

FROM balenalib/raspberry-pi-debian-python:3.7-buster-build as build-armv6

ENV LANG C.UTF-8

RUN apt-get update && \
    apt-get install --no-install-recommends --yes \
        swig libatlas-base-dev portaudio19-dev

# -----------------------------------------------------------------------------

ARG TARGETARCH
ARG TARGETVARIANT
FROM build-$TARGETARCH$TARGETVARIANT as build

ENV APP_DIR=/usr/lib/voice2json
ENV BUILD_DIR=/build

# Directory of prebuilt tools
COPY download/ ${BUILD_DIR}/download/

COPY m4/ ${BUILD_DIR}/m4/
COPY configure config.sub config.guess \
     install-sh missing aclocal.m4 \
     Makefile.in setup.py.in voice2json.sh.in voice2json.spec.in \
     requirements.txt \
     ${BUILD_DIR}/

RUN cd ${BUILD_DIR} && \
    ./configure --prefix=${APP_DIR}

COPY scripts/install/ ${BUILD_DIR}/scripts/install/

COPY etc/profile.defaults.yml ${BUILD_DIR}/etc/
COPY etc/precise/ ${BUILD_DIR}/etc/precise/
COPY site/ ${BUILD_DIR}/site/

COPY VERSION README.md LICENSE ${BUILD_DIR}/
COPY voice2json/ ${BUILD_DIR}/voice2json/

RUN cd ${BUILD_DIR} && \
    make && \
    make install

# Strip binaries and shared libraries
RUN (find ${APP_DIR} -type f \( -name '*.so*' -or -executable \) -print0 | xargs -0 strip --strip-unneeded -- 2>/dev/null) || true

# -----------------------------------------------------------------------------

FROM ubuntu:eoan as run

ENV LANG C.UTF-8

RUN apt-get update && \
    apt-get install --yes --no-install-recommends \
        python3 \
        libportaudio2 libatlas3-base libgfortran4 \
        ca-certificates \
        perl sox alsa-utils espeak jq

# -----------------------------------------------------------------------------

FROM run as run-amd64

FROM run as run-armv7

FROM run as run-arm64

FROM balenalib/raspberry-pi-debian-python:3.7-buster-run as run-armv6

ENV LANG C.UTF-8

RUN install_packages \
        libportaudio2 libatlas3-base libgfortran4 \
        ca-certificates \
        perl sox alsa-utils espeak jq

# -----------------------------------------------------------------------------

ARG TARGETARCH
ARG TARGETVARIANT
FROM run-$TARGETARCH$TARGETVARIANT

ENV APP_DIR=/usr/lib/voice2json
COPY --from=build ${APP_DIR}/ ${APP_DIR}/

RUN cp ${APP_DIR}/bin/voice2json /usr/bin/

ENTRYPOINT ["bash", "/usr/bin/voice2json"]