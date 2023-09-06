FROM debian:bookworm-slim as builder
ENV DEBIAN_FRONTEND=noninteractive

ARG ARCH
ARG BITCOIN_VERSION
ARG REPO
ARG BRANCH
ARG BITCOIN_URL

# Base requirements
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        wget \
    && apt-get clean

# Download binary
RUN if [ -n "${BITCOIN_URL}" ]; then \
        wget "${BITCOIN_URL}/bitcoin-core-${BITCOIN_VERSION}/bitcoin-${BITCOIN_VERSION}-${ARCH}-linux-gnu.tar.gz"; \
        tar -xzf "bitcoin-${BITCOIN_VERSION}-${ARCH}-linux-gnu.tar.gz" -C /usr/local --strip-components=1; \
    fi;

# Extra requirements to build from source
RUN if [ -n "${REPO}" ]; then \
        apt-get update && apt-get install -y \
            automake \
            autotools-dev \
            build-essential \
            git \
            libtool \
            libboost-dev \
            libevent-dev \
            libdb5.3++-dev \
            libminiupnpc-dev \
            libnatpmp-dev \
            libzmq3-dev \
            libqrencode-dev \
            libsqlite3-dev \
            pkg-config \
        && apt-get clean; \
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

RUN rm -f /usr/local/bin/bitcoin-qt
RUN rm -f /usr/local/bin/test_bitcoin*

# shrink image size a bit with a second stage
FROM debian:bookworm-slim

ARG UID=3338
ARG GID=3338
ARG REPO
# env var overrides
ENV UID=$UID
ENV GID=$GID

ENV BITCOIN_DATA=/home/bitcoin/.bitcoin

RUN groupadd --gid ${GID} bitcoin \
  && useradd --create-home --no-log-init -u ${UID} -g ${GID} bitcoin \
  && apt-get update && apt-get install -y --no-install-recommends \
        gosu \
        tor \
        iproute2; \
    apt-get clean;

# libs needed to run source-build without depends
RUN if [ -n "${REPO}" ]; then \
        apt-get update && apt-get install -y \
            libboost-dev \
            libevent-dev \
            libdb5.3++-dev \
            libminiupnpc-dev \
            libnatpmp-dev \
            libzmq3-dev \
            libqrencode-dev \
            libsqlite3-dev \
        && apt-get clean; \
    fi;

COPY --from=builder /usr/local/bin/bitcoin* /usr/local/bin/

COPY docker-entrypoint.sh /entrypoint.sh
COPY tor-keys/* /home/debian-tor/.tor/keys/

VOLUME ["/home/bitcoin/.bitcoin"]

EXPOSE 8332 8333 18332 18333 18443 18444 38333 38332

ENTRYPOINT ["/entrypoint.sh"]

RUN bitcoind -version | grep -E "Bitcoin Core( Daemon)? version v${BITCOIN_VERSION}"

CMD ["bitcoind"]
