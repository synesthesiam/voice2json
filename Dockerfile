FROM pumpkin.lan:15555/voice2json-build as build

ENV LANG C.UTF-8

ENV APP_DIR=/usr/lib/voice2json
ENV APP_VENV=/usr/lib/voice2json/.venv

# Directory of prebuilt tools
COPY download/ ${APP_DIR}/download/

# Cache pip downloads
COPY configure config.sub config.guess \
     install-sh missing aclocal.m4 \
     Makefile.in setup.py.in voice2json.sh.in ${APP_DIR}/
COPY m4/ ${APP_DIR}/m4/

RUN cd ${APP_DIR} && \
    ./configure --prefix=${APP_VENV}

COPY scripts/install/ ${APP_DIR}/scripts/install/
COPY requirements.txt ${APP_DIR}/

RUN cd ${APP_DIR} && \
    make && \
    make install-init && \
    make install-dependencies

COPY etc/profile.defaults.yml ${APP_DIR}/etc/
COPY etc/precise/ ${APP_DIR}/etc/precise/
COPY site/ ${APP_DIR}/site/

COPY README.md LICENSE VERSION ${APP_DIR}/
COPY voice2json/ ${APP_DIR}/voice2json/

RUN cd ${APP_DIR} && \
    make install-voice2json

# Strip binaries and shared libraries
RUN (find ${APP_VENV} -type f \( -name '*.so*' -or -executable \) -print0 | xargs -0 strip --strip-unneeded -- 2>/dev/null) || true

# -----------------------------------------------------------------------------
# Runtime Image
# -----------------------------------------------------------------------------

FROM pumpkin.lan:15555/voice2json-run

ENV LANG C.UTF-8
ENV APP_DIR=/usr/lib/voice2json
ENV APP_VENV=${APP_DIR}/.venv

# Copy Rhasspy virtual environment
COPY --from=build ${APP_VENV}/ ${APP_VENV}/
RUN cp -a ${APP_VENV}/bin/voice2json /usr/bin/

ENTRYPOINT ["bash", "/usr/lib/voice2json/.venv/bin/voice2json"]