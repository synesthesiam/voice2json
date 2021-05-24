FROM debian:buster as build

ENV LANG C.UTF-8
ENV DEBIAN_FRONTEND=noninteractive

RUN --mount=type=cache,id=apt-build,target=/var/apt/cache \
    apt-get update && \
    apt-get install --no-install-recommends --yes \
        python3 python3-dev python3-setuptools python3-pip python3-venv \
        build-essential swig libatlas-base-dev portaudio19-dev \
        curl ca-certificates

ENV APP_DIR=/usr/lib/voice2json
ENV BUILD_DIR=/build

# Directory of prebuilt tools
ARG TARGETARCH
ARG TARGETVARIANT
COPY download/shared ${BUILD_DIR}/download/
COPY download/${TARGETARCH}${TARGETVARIANT}/ ${BUILD_DIR}/download/

COPY m4/ ${BUILD_DIR}/m4/
COPY configure config.sub config.guess \
     install-sh missing aclocal.m4 \
     Makefile.in setup.py.in voice2json.sh.in voice2json.spec.in \
     requirements.txt \
     ${BUILD_DIR}/

RUN cd ${BUILD_DIR} && \
    ./configure --enable-in-place --prefix=${APP_DIR}/.venv

COPY scripts/install/ ${BUILD_DIR}/scripts/install/

RUN --mount=type=cache,id=pip-build,target=/root/.cache/pip \
    cd ${BUILD_DIR} && \
    make && \
    make install

# -----------------------------------------------------------------------------

FROM debian:buster as run

ENV LANG C.UTF-8

RUN --mount=type=cache,id=apt-run,target=/var/apt/cache \
    apt-get update && \
    apt-get install --yes --no-install-recommends \
        python3 \
        libportaudio2 libatlas3-base libgfortran4 \
        ca-certificates \
        perl sox alsa-utils espeak jq

ENV APP_DIR=/usr/lib/voice2json
COPY --from=build ${APP_DIR}/ ${APP_DIR}/
COPY --from=build /build/voice2json.sh ${APP_DIR}/

COPY etc/profile.defaults.yml ${APP_DIR}/etc/
COPY etc/precise/ ${APP_DIR}/etc/precise/
COPY site/ ${APP_DIR}/site/
COPY bin/voice2json ${APP_DIR}/bin/

COPY VERSION ${APP_DIR}/
COPY voice2json/ ${APP_DIR}/voice2json/

ENTRYPOINT ["bash", "/usr/lib/voice2json/voice2json.sh"]
