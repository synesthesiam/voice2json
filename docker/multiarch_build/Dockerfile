ARG BUILD_FROM
FROM $BUILD_FROM

ARG MAKE_THREADS=8
ARG DEBIAN_ARCH
ARG CPU_ARCH

ENV LANG C.UTF-8

COPY docker/multiarch_build/bin/qemu-* /usr/bin/

RUN apt-get update && \
    apt-get install -y \
        python3 python3-dev python3-pip python3-venv \
        build-essential \
        autoconf automake libtool \
        bison swig \
        libssl-dev libacl1-dev liblz4-dev libfuse-dev fuse pkg-config \
        fakeroot build-essential wget \
        zlib1g-dev libbz2-dev libncurses5-dev \
        libreadline-dev liblzma-dev libsqlite3-dev \
        curl subversion rsync \
        libatlas-base-dev libatlas3-base \
        sox git unzip python2.7

# -----------------------------------------------------------------------------

RUN cd / && \
    wget https://github.com/pyinstaller/pyinstaller/releases/download/v3.5/PyInstaller-3.5.tar.gz && \
    tar -xf /PyInstaller-3.5.tar.gz

RUN cd /PyInstaller-3.5/bootloader && \
    python3 ./waf all --no-lsb

RUN cd /PyInstaller-3.5 && \
    python3 -m pip install -e .

# -----------------------------------------------------------------------------

# Fake sudo
COPY docker/multiarch_build/bin/sudo /usr/bin/

ENTRYPOINT ["bash"]
