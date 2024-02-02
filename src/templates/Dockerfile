FROM debian:bookworm-slim as builder
ENV DEBIAN_FRONTEND=noninteractive

ARG ARCH
ARG BITCOIN_VERSION
ARG REPO
ARG BRANCH
ARG BUILD_ARGS
ARG BITCOIN_URL

# install or build
RUN set -ex \
    && apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        wget \
    && if [ -n "${BITCOIN_URL}" ]; then \
        wget "${BITCOIN_URL}/bitcoin-core-${BITCOIN_VERSION}/bitcoin-${BITCOIN_VERSION}-${ARCH}.tar.gz"; \
        tar -xzf "bitcoin-${BITCOIN_VERSION}-${ARCH}.tar.gz" -C /usr/local --strip-components=1; \
    fi \
    && if [ -n "${REPO}" ]; then \
        apt-get install -y \
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
            pkg-config; \
        mkdir build; \
        cd /build; \
        git clone --depth 1 --branch "${BRANCH}" "https://github.com/${REPO}"; \
        cd /build/bitcoin; \
        ./autogen.sh; \
        ./configure ${BUILD_ARGS}; \
        make -j$(nproc); \
        make install; \
    fi

# shrink image size with a second stage
FROM debian:bookworm-slim

ARG UID=3338
ARG GID=3338
ARG REPO
ARG TOR=0
ARG WARNET=0
ARG BITCOIN_ARGS
# env var overrides
ENV UID=$UID
ENV GID=$GID
ENV BITCOIN_DATA=/home/bitcoin/.bitcoin
ENV BITCOIN_ARGS=$BITCOIN_ARGS
ENV TOR=$TOR
ENV WARNET=$WARNET

RUN set -ex \
    && groupadd --gid ${GID} bitcoin \
    && useradd --create-home --no-log-init -u ${UID} -g ${GID} bitcoin \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        dnsutils \
        gosu \
        iproute2 \
        tor \
    && if [ -n "${REPO}" ]; then \
        apt-get install -y --no-install-recommends \
            libboost-dev \
            libevent-dev \
            libdb5.3++-dev \
            libminiupnpc-dev \
            libnatpmp-dev \
            libzmq3-dev \
            libqrencode-dev \
            libsqlite3-dev; \
    fi \
    && apt-get clean \
    && rm -rf /var/cache/apt/* /var/lib/apt/lists/*

COPY --from=builder /usr/local/bin/bitcoind /usr/local/bin/bitcoin-cli /usr/local/bin/
COPY entrypoint.sh /entrypoint.sh
# Warnet torrc using test network
COPY tor/torrc /etc/tor/warnet-torr

VOLUME ["/home/bitcoin/.bitcoin"]
EXPOSE 8332 8333 18332 18333 18443 18444 38333 38332

ENTRYPOINT ["/entrypoint.sh"]
RUN bitcoind -version | grep -E "Bitcoin Core( Daemon)? version v${BITCOIN_VERSION}"
CMD ["bitcoind"]
