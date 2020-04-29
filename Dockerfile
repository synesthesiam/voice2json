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

COPY configure config.sub config.guess \
     install-sh missing aclocal.m4 \
     Makefile.in setup.py.in voice2json.sh.in ${APP_DIR}/
COPY m4/ ${APP_DIR}/m4/

RUN cd ${APP_DIR} && \
    ./configure --prefix=${APP_VENV}

COPY download/ ${APP_DIR}/download/
COPY scripts/install/ ${APP_DIR}/scripts/install/

COPY README.md LICENSE VERSION requirements.txt ${APP_DIR}/
COPY voice2json/ ${APP_DIR}/voice2json/

RUN cd ${APP_DIR} && \
    make && \
    make install

# Strip binaries
RUN strip --strip-unneeded -- ${APP_VENV}/bin/* 2>/dev/null || true
RUN (find ${APP_VENV}/lib -type f -name '*.so*' -print0 | xargs -0 strip --strip-unneeded -- 2>/dev/null) || true

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