FROM ubuntu:20.04
ENV DEBIAN_FRONTEND=noninteractive

ARG ARCH
ARG BITCOIN_URL
ARG BITCOIN_VERSION
ARG REPO
ARG BRANCH

# Base requirements
RUN apt-get update && apt-get install -y \
        ccache \
        python3 \
        vim \
        build-essential \
        wget \
        tor \
        iproute2; \
    apt-get clean;

# Download binary
RUN if [ -n "${BITCOIN_URL}" ]; then \
        wget "${BITCOIN_URL}"; \
        tar -xzf "bitcoin-${BITCOIN_VERSION}-${ARCH}-linux-gnu.tar.gz" -C /usr/local --strip-components=1; \
    fi;

# Extra requirements to build from source
RUN if [ -n "${REPO}" ]; then \
        apt-get install -y \
            autotools-dev \
            libtool \
            automake \
            pkg-config \
            libboost-dev \
            libevent-dev \
            libdb5.3++-dev \
            libminiupnpc-dev \
            libnatpmp-dev \
            libzmq3-dev \
            libqrencode-dev \
            libsqlite3-dev \
            git; \
        apt-get clean; \
    fi;

# Build from source
RUN if [ -n "${REPO}" ]; then \
        mkdir build; \
        cd /build; \
        git clone --depth 1 --branch "${BRANCH}" "https://github.com/${REPO}"; \
        cd /build/bitcoin; \
        ./autogen.sh; \
        ./configure \
            --disable-tests \
            --without-gui \
            --disable-bench \
            --disable-fuzz-binary \
            --enable-suppress-external-warnings; \
        make -j$(nproc); \
        make install; \
    fi;

# Start tor and the Bitcoin Core daemon.
CMD tor && \
    /usr/local/bin/bitcoind --datadir=/root/.bitcoin --conf=/root/.bitcoin/bitcoin.conf
