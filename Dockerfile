

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
ARG ARCH
ARG BITCOIN_URL
ARG BITCOIN_VERSION

# Download, verify, and install Bitcoin Core.
RUN wget $BITCOIN_URL && \
    tar -xzf bitcoin-${BITCOIN_VERSION}-${ARCH}-linux-gnu.tar.gz -C /usr/local --strip-components=1

# Create a directory for Bitcoin data and set it as the working directory.
RUN mkdir /bitcoin

WORKDIR /bitcoin
COPY config/bitcoin.conf .


# Expose necessary ports for the Bitcoin service.
#EXPOSE 18444 18443
#EXPOSE 8332 8333

# Start the Bitcoin Core daemon.
# CMD ["/usr/local/bin/bitcoind --datadir=/root/.bitcoin --conf=/root/.bitcoin/bitcoin.conf"]
CMD ["/usr/local/bin/bitcoind", "--datadir=/bitcoin", "--conf=/bitcoin/bitcoin.conf"]

