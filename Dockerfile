FROM ubuntu:eoan as build
ARG TARGETPLATFORM
ARG TARGETARCH
ARG TARGETVARIANT

ENV LANG C.UTF-8

RUN apt-get update && \
    apt-get install --no-install-recommends --yes \
        python3 python3-dev python3-setuptools python3-pip python3-venv \
        build-essential swig libatlas-base-dev portaudio19-dev

# Build virtual environment
ENV APP_DIR=/usr/lib/voice2json
ENV APP_VENV=${APP_DIR}/.venv
ENV APP_PIP=${APP_VENV}/bin/pip3

COPY requirements.txt ${APP_DIR}/
RUN python3 -m venv ${APP_VENV}
RUN ${APP_PIP} install wheel setuptools

# Pocketsphinx without Pulseaudio dependency
COPY download/pocketsphinx-python.tar.gz /
RUN ${APP_PIP} install /pocketsphinx-python.tar.gz

# Exclude DeepSpeech from arm64
RUN if [ "$TARGETARCH" = "arm64" ]; then sed -i '/^deepspeech/d' ${APP_DIR}/requirements.txt; fi

# Runtime Python dependencies
RUN ${APP_PIP} install -r ${APP_DIR}/requirements.txt

# Create directory for pre-built binaries
RUN mkdir -p ${APP_VENV}/tools

# Phonetisuarus
ADD download/phonetisaurus-2019-${TARGETARCH}${TARGETVARIANT}.tar.gz /phonetisaurus/
RUN cd /phonetisaurus && mv bin/* ${APP_VENV}/tools/ && mv lib/* ${APP_VENV}/tools/

# Kaldi
ADD download/kaldi-2020-${TARGETARCH}${TARGETVARIANT}.tar.gz ${APP_VENV}/tools/

# Mycroft Precise Engine
ADD download/precise-engine_0.3.0_${TARGETARCH}${TARGETVARIANT}.tar.gz ${APP_VENV}/tools/

# Mozilla DeepSpeech (excludes arm64)
COPY download/native_client.${TARGETARCH}${TARGETVARIANT}.cpu.linux.0.6.1.tar.xz /native_client.tar.xz
RUN if [ "$TARGETARCH" != "arm64" ]; then tar -C ${APP_VENV}/tools -xf /native_client.tar.xz; fi

# KenLM (excludes arm64)
COPY download/kenlm-20200308_${TARGETARCH}${TARGETVARIANT}.tar.gz /kenlm.tar.gz
RUN if [ "$TARGETARCH" != "arm64" ]; then tar -C ${APP_VENV}/tools -xf /kenlm.tar.gz; fi

# Julius (excludes arm64)
COPY download/julius_4.5_${TARGETARCH}${TARGETVARIANT}.tar.gz /julius.tar.gz
RUN if [ "$TARGETARCH" != "arm64" ]; then tar -C ${APP_VENV}/tools -xf /julius.tar.gz; fi

# -----------------------------------------------------------------------------
# Runtime Image
# -----------------------------------------------------------------------------

FROM ubuntu:eoan
ARG TARGETPLATFORM
ARG TARGETARCH
ARG TARGETVARIANT

ENV LANG C.UTF-8
ENV APP_DIR=/usr/lib/voice2json
ENV APP_VENV=${APP_DIR}/.venv

# Install Debian dependencies
RUN apt-get update && \
    apt-get install --no-install-recommends --yes \
    libportaudio2 libatlas3-base python3 python3-dev \
    libfst-tools libngram-tools \
    libgfortran4 ca-certificates \
    perl sox alsa-utils espeak

# Copy Rhasspy virtual environment
COPY --from=build ${APP_VENV} ${APP_VENV}

COPY VERSION ${APP_DIR}/
COPY voice2json.sh ${APP_DIR}/

# Copy source
COPY voice2json/ ${APP_DIR}/voice2json

WORKDIR ${APP_DIR}

ENTRYPOINT ["voice2json.sh"]