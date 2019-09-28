ARG BUILD_FROM
FROM $BUILD_FROM

ARG MAKE_THREADS=8
ARG DEBIAN_ARCH
ARG CPU_ARCH

ENV LANG C.UTF-8

COPY docker/multiarch_build/bin/qemu-* /usr/bin/

RUN apt-get update && \
    apt-get install -y \
        build-essential \
        autoconf automake libtool \
        bison swig \
        libssl-dev libacl1-dev liblz4-dev libfuse-dev fuse pkg-config \
        fakeroot build-essential wget \
        zlib1g-dev libbz2-dev libncurses5-dev \
        libreadline-dev liblzma-dev libsqlite3-dev \
        curl subversion

COPY download/ /download/
COPY docker/multiarch_build/bin/sudo /usr/bin/
COPY etc/shflags /etc/
COPY install.sh /
COPY requirements.txt /

WORKDIR /
RUN bash install.sh \
    --nocreate --noruntime \
    --download-dir /download \
    --make-threads ${MAKE_THREADS}

# -----------------------------------------------------------------------------

RUN cd / && \
    wget https://github.com/pyinstaller/pyinstaller/releases/download/v3.5/PyInstaller-3.5.tar.gz && \
    tar -xf /PyInstaller-3.5.tar.gz

RUN cd /PyInstaller-3.5/bootloader && \
    python3 ./waf all --no-lsb

RUN cd /PyInstaller-3.5 && \
    python3 -m pip install -e .

# -----------------------------------------------------------------------------

ENTRYPOINT ["bash"]
