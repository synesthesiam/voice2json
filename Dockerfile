ARG DOCKER_REGISTRY=docker.io
FROM ${DOCKER_REGISTRY}/voice2json-run as build

RUN apt-get update && \
    apt-get install --yes --no-install-recommends \
        dpkg-dev

COPY dist/ /dist/
COPY VERSION /

RUN export DEBIAN_ARCH="$(dpkg-architecture | grep DEB_BUILD_ARCH= | sed -e 's/[^=]\+=//')" && \
    export VERSION="$(cat /VERSION)" && \
    apt install --yes --no-install-recommends \
        /dist/voice2json_${VERSION}_${DEBIAN_ARCH}.deb

# Sanity check
RUN voice2json --version

# -----------------------------------------------------------------------------

ARG DOCKER_REGISTRY=docker.io
FROM ${DOCKER_REGISTRY}/voice2json-run

ENV APP_PREFIX=/usr
COPY --from=build ${APP_PREFIX}/lib/voice2json/ ${APP_PREFIX}/lib/voice2json/
COPY --from=build ${APP_PREFIX}/bin/voice2json ${APP_PREFIX}/bin/

ENTRYPOINT ["bash", "/usr/bin/voice2json"]