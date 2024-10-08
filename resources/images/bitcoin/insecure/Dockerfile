# Base stage
# ----------
#
# We use the alpine version to get the
# correct version of glibc / gcc for building older bitcoin
# core versions.

# Default is set here to quiet a warning from Docker, but the caller must
# be sure to ALWAYS set this correct per the version of bitcoin core they are
# trying to build
ARG ALPINE_VERSION=3.7
FROM alpine:${ALPINE_VERSION} AS base

# Setup deps stage
# ----------------
#
# this installs the common dependencies for all of the old versions
# and then version specific dependencies are passed via the
# EXTRA_PACKAGES ARG
FROM base AS deps
ARG EXTRA_PACKAGES=""
RUN --mount=type=cache,target=/var/cache/apk \
    sed -i 's/http\:\/\/dl-cdn.alpinelinux.org/https\:\/\/alpine.global.ssl.fastly.net/g' /etc/apk/repositories \
    && apk --no-cache add \
    autoconf \
    automake \
    boost-dev \
    build-base \
    ccache \
    chrpath \
    file \
    gnupg \
    git \
    libevent-dev \
    libressl \
    libtool \
    linux-headers \
    zeromq-dev \
    ${EXTRA_PACKAGES}

ENV BERKELEYDB_VERSION=db-4.8.30.NC
ENV BERKELEYDB_PREFIX=/opt/${BERKELEYDB_VERSION}

RUN wget https://download.oracle.com/berkeley-db/${BERKELEYDB_VERSION}.tar.gz
RUN tar -xzf *.tar.gz
RUN sed s/__atomic_compare_exchange/__atomic_compare_exchange_db/g -i ${BERKELEYDB_VERSION}/dbinc/atomic.h
RUN mkdir -p ${BERKELEYDB_PREFIX}

WORKDIR /${BERKELEYDB_VERSION}/build_unix

RUN ../dist/configure --enable-cxx --disable-shared --with-pic --prefix=${BERKELEYDB_PREFIX}
RUN make -j$(nproc)
RUN make install
RUN rm -rf ${BERKELEYDB_PREFIX}/docs

# Build stage
# -----------
#
# We can build from a git repo using the REPO and COMMIT_SHA args
# or from a local directory using FROM_SRC=true and specifying the local
# source directory. Build args are set using a default but can be changed
# on an imnage by image basis, if needed
#
# PRE_CONFIGURE_COMMANDS is used for version specific fixes needed before
# running ./autogen.sh && ./configure
#
# EXTRA_BUILD_ARGS is used for version specific build flags
FROM deps AS build
ARG FROM_SRC="false"
ARG REPO=""
ARG COMMIT_SHA=""
ARG BUILD_ARGS="--disable-tests --without-gui --disable-bench --disable-fuzz-binary --enable-suppress-external-warnings"
ARG EXTRA_BUILD_ARGS=""
ARG PRE_CONFIGURE_COMMANDS=""

COPY --from=deps /opt /opt
ENV BITCOIN_PREFIX=/opt/bitcoin
WORKDIR /build

# Even if not being used, --build-context bitcoin-src must be specified else
# this line will error. If building from a remote repo, use something like
# --build-context bitcoin-src="."
COPY --from=bitcoin-src . /tmp/bitcoin-source
RUN if [ "$FROM_SRC" = "true" ]; then \
        # run with --progress=plain to see these log outputs
        echo "Using local files from /tmp/bitcoin-source"; \
        if [ -d "/tmp/bitcoin-source" ] && [ "$(ls -A /tmp/bitcoin-source)" ]; then \
            cp -R /tmp/bitcoin-source /build/bitcoin; \
        else \
            echo "Error: Local source directory is empty or does not exist" && exit 1; \
        fi \
    else \
        echo "Cloning from git repository"; \
        git clone --depth 1 "https://github.com/${REPO}" /build/bitcoin \
        && cd /build/bitcoin \
        && git fetch --depth 1 origin "$COMMIT_SHA" \
        && git checkout "$COMMIT_SHA"; \
    fi;

# This is not our local ccache, but ccache in the docker cache
# this does speed up builds substantially when building from source or building
# multiple versions sequentially
ENV CCACHE_DIR=/ccache
RUN --mount=type=cache,target=/ccache \
    set -ex \
    && cd /build/bitcoin \
    && if [ -n "$PRE_CONFIGURE_COMMANDS" ]; then \
         eval ${PRE_CONFIGURE_COMMANDS}; \
       fi \
    && ./autogen.sh \
    && ./configure \
    LDFLAGS=-L`ls -d /opt/db*`/lib/ \
    CPPFLAGS="-I`ls -d /opt/db*`/include/ --param ggc-min-expand=1 --param ggc-min-heapsize=32768" \
    --prefix=${BITCOIN_PREFIX} \
    ${BUILD_ARGS} \
    ${EXTRA_BUILD_ARGS} \
    --with-daemon \
    && make -j$(nproc) \
    && make install \
    && strip ${BITCOIN_PREFIX}/bin/bitcoin-cli \
    && strip ${BITCOIN_PREFIX}/bin/bitcoind \
    && rm -f ${BITCOIN_PREFIX}/lib/libbitcoinconsensus.a \
    && rm -f ${BITCOIN_PREFIX}/lib/libbitcoinconsensus.so.0.0.0 \
    && rm -f ${BITCOIN_PREFIX}/bin/bitcoin-tx \
    && rm -f ${BITCOIN_PREFIX}/bin/bitcoin-wallet

# verify ccache is working, specify --progress=plain to see output in build logs
RUN ccache -s

# Final clean stage
# -----------------
#
# EXTRA_RUNTIME_PACKAGES is used for version specific runtime deps
FROM alpine:${ALPINE_VERSION}
ARG EXTRA_RUNTIME_PACKAGES=""
ARG UID=100
ARG GID=101
ARG BITCOIN_VERSION
ENV BITCOIN_DATA=/root/.bitcoin
ENV BITCOIN_PREFIX=/opt/bitcoin
ENV PATH=${BITCOIN_PREFIX}/bin:$PATH
ENV BITCOIN_VERSION=${BITCOIN_VERSION}
LABEL maintainer.0="bitcoindevproject"

RUN addgroup -g ${GID} -S bitcoin
RUN adduser -u ${UID} -S bitcoin -G bitcoin
RUN --mount=type=cache,target=/var/cache/apk sed -i 's/http\:\/\/dl-cdn.alpinelinux.org/https\:\/\/alpine.global.ssl.fastly.net/g' /etc/apk/repositories \
    && apk --no-cache add \
    bash \
    boost-filesystem \
    boost-system \
    boost-thread \
    libevent \
    libzmq \
    shadow \
    sqlite-dev \
    su-exec \
    ${EXTRA_RUNTIME_PACKAGES}

COPY --from=build /opt/bitcoin /usr/local
COPY entrypoint.sh /entrypoint.sh

VOLUME ["/home/bitcoin/.bitcoin"]
EXPOSE 8332 8333 18332 18333 18443 18444 38333 38332

ENTRYPOINT ["/entrypoint.sh"]
CMD ["bitcoind"]

