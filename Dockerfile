

# Use a base image that has the necessary dependencies.
FROM ubuntu:20.04

# Set environment variables to avoid prompts.
ENV DEBIAN_FRONTEND=noninteractive

# Update and install necessary packages.
RUN apt-get update && apt-get install -y \
    ccache \
    python3 \
    vim \
    build-essential \
# #     libtool \
# #     autotools-dev \
# #     automake \
# #     pkg-config \
# #     bsdmainutils \
# #     python3 \
# #     libevent-dev \
# #     libboost-system-dev \
# #     libboost-filesystem-dev \
# #     libboost-test-dev \
    wget && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set arguments for Bitcoin version and download URLs.
ARG BITCOIN_VERSION
ARG BITCOIN_BIN_URL=https://bitcoincore.org/bin/bitcoin-core-${BITCOIN_VERSION}/bitcoin-${BITCOIN_VERSION}-aarch64-linux-gnu.tar.gz
ARG BITCOIN_SIG_URL=https://bitcoincore.org/bin/bitcoin-core-${BITCOIN_VERSION}/SHA256SUMS.asc

# Download, verify, and install Bitcoin Core.
RUN wget $BITCOIN_BIN_URL && \
    wget $BITCOIN_SIG_URL && \
    tar -xzf bitcoin-${BITCOIN_VERSION}-aarch64-linux-gnu.tar.gz -C /usr/local --strip-components=1 && \
    rm bitcoin-${BITCOIN_VERSION}-aarch64-linux-gnu.tar.gz SHA256SUMS.asc

# Create a directory for Bitcoin data and set it as the working directory.
RUN mkdir /bitcoin

WORKDIR /bitcoin
COPY config/bitcoin.conf .


# Expose necessary ports for the Bitcoin service.
EXPOSE 18332 18333
EXPOSE 8332 8333

# Start the Bitcoin Core daemon.
# CMD ["/usr/local/bin/bitcoind --datadir=/root/.bitcoin --conf=/root/.bitcoin/bitcoin.conf"]
CMD ["/usr/local/bin/bitcoind", "--datadir=/bitcoin", "--conf=/bitcoin/bitcoin.conf"]

