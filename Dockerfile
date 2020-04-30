ARG TARGETPLATFORM
ARG TARGETARCH
ARG TARGETVARIANT
FROM $TARGETARCH$TARGETVARIANT/voice2json-build as build
ARG TARGETPLATFORM
ARG TARGETARCH
ARG TARGETVARIANT

ENV LANG C.UTF-8

ENV APP_DIR=/usr/lib/voice2json
ENV APP_VENV=/usr/lib/voice2json/.venv

# Directory of prebuilt tools
COPY download/ ${APP_DIR}/download/

# Cache pip downloads
COPY requirements.txt ${APP_DIR}/
RUN pip3 download --dest /pipcache pip wheel setuptools
RUN pip3 download --dest /pipcache -r ${APP_DIR}/requirements.txt

COPY configure config.sub config.guess \
     install-sh missing aclocal.m4 \
     Makefile.in setup.py.in voice2json.sh.in ${APP_DIR}/
COPY m4/ ${APP_DIR}/m4/

RUN cd ${APP_DIR} && \
    ./configure --prefix=${APP_VENV}

COPY scripts/install/ ${APP_DIR}/scripts/install/

COPY etc/profile.defaults.yml ${BUILD_DIR}/etc/
COPY etc/precise/ ${BUILD_DIR}/etc/precise/
COPY site/ ${BUILD_DIR}/site/

RUN export PIP_INSTALL_ARGS="-f /pipcache --no-index" && \
    cd ${APP_DIR} && \
    make && \
    make install-init && \
    make install-dependencies

COPY README.md LICENSE VERSION ${APP_DIR}/
COPY voice2json/ ${APP_DIR}/voice2json/
RUN cd ${APP_DIR} && \
    make install-voice2json

# Strip binaries and shared libraries
RUN (find ${APP_VENV} -type f \( -name '*.so*' -or -type x \) -print0 | xargs -0 strip --strip-unneeded -- 2>/dev/null) || true

# -----------------------------------------------------------------------------
# Runtime Image
# -----------------------------------------------------------------------------

ARG TARGETPLATFORM
ARG TARGETARCH
ARG TARGETVARIANT
FROM $TARGETARCH$TARGETVARIANT/voice2json-run
ARG TARGETPLATFORM
ARG TARGETARCH
ARG TARGETVARIANT

ENV LANG C.UTF-8
ENV APP_DIR=/usr/lib/voice2json
ENV APP_VENV=${APP_DIR}/.venv

# Copy Rhasspy virtual environment
COPY --from=build ${APP_VENV} ${APP_VENV}
COPY ${APP_VENV}/bin/voice2json /usr/bin/

COPY README.md LICENSE VERSION ${APP_DIR}/

# Copy source
COPY voice2json/ ${APP_DIR}/voice2json/

# Copy documentation
COPY site/ ${APP_DIR}/site/

ENTRYPOINT ["bash", "/usr/lib/voice2json/.venv/bin/voice2json"]