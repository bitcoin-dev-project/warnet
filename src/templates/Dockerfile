# Setup deps stage
FROM alpine as deps
ARG REPO
ARG BRANCH
ARG BUILD_ARGS

RUN --mount=type=cache,target=/var/cache/apk \
    sed -i 's/http\:\/\/dl-cdn.alpinelinux.org/https\:\/\/alpine.global.ssl.fastly.net/g' /etc/apk/repositories \
    && apk --no-cache add \
    autoconf \
    automake \
    boost-dev \
    build-base \
    chrpath \
    file \
    gnupg \
    git \
    libevent-dev \
    libressl \
    libtool \
    linux-headers \
    sqlite-dev \
    zeromq-dev

COPY src/templates/isroutable.patch /tmp/
COPY src/templates/addrman.patch /tmp/


# Clone and patch and build stage
FROM deps as build
ENV BITCOIN_PREFIX=/opt/bitcoin
WORKDIR /build

RUN set -ex \
    && cd /build \
    && git clone --depth 1 --branch "${BRANCH}" "https://github.com/${REPO}" \
    && cd bitcoin \
    && git apply /tmp/isroutable.patch \
    && git apply /tmp/addrman.patch \
    && sed -i s:sys/fcntl.h:fcntl.h: src/compat/compat.h \
    && ./autogen.sh \
    && ./configure \
    LDFLAGS=-L`ls -d /opt/db*`/lib/ \
    CPPFLAGS=-I`ls -d /opt/db*`/include/ \
    --prefix=${BITCOIN_PREFIX} \
    ${BUILD_ARGS} \
    && make -j$(nproc) \
    && make install \
    && strip ${BITCOIN_PREFIX}/bin/bitcoin-cli \
    && strip ${BITCOIN_PREFIX}/bin/bitcoind \
    && strip ${BITCOIN_PREFIX}/lib/libbitcoinconsensus.a \
    && strip ${BITCOIN_PREFIX}/lib/libbitcoinconsensus.so.0.0.0 \
    && rm ${BITCOIN_PREFIX}/bin/bitcoin-tx \
    && rm ${BITCOIN_PREFIX}/bin/bitcoin-wallet \
    && rm ${BITCOIN_PREFIX}/bin/bitcoin-util

# Final clean stage
FROM alpine
ARG UID=100
ARG GID=101
ENV BITCOIN_DATA=/root/.bitcoin
ENV BITCOIN_PREFIX=/opt/bitcoin
ENV PATH=${BITCOIN_PREFIX}/bin:$PATH
LABEL maintainer.0="bitcoindevproject"

RUN addgroup bitcoin --gid ${GID} --system \
    && adduser --uid ${UID} --system bitcoin --ingroup bitcoin
RUN --mount=type=cache,target=/var/cache/apk sed -i 's/http\:\/\/dl-cdn.alpinelinux.org/https\:\/\/alpine.global.ssl.fastly.net/g' /etc/apk/repositories \
    && apk --no-cache add \
    bash \
    libevent \
    libzmq \
    shadow \
    sqlite-dev \
    su-exec \
    tor

COPY --from=build /opt/bitcoin /usr/local
COPY src/templates/entrypoint.sh /entrypoint.sh
COPY src/templates/tor/torrc.relay /etc/tor/torrc

RUN chown -R bitcoin:bitcoin /etc/tor
RUN chown -R bitcoin /var/log/tor

VOLUME ["/home/bitcoin/.bitcoin"]
EXPOSE 8332 8333 18332 18333 18443 18444 38333 38332

ENTRYPOINT ["/entrypoint.sh"]
CMD ["bitcoind"]

