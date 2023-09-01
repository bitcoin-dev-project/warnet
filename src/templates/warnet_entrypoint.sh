#!/bin/bash
# Custom warnet entrypoint instructions, will be run before base image entrypoint.sh

# bitcoin
usermod -a -G debian-tor bitcoin

# tor
cp /etc/tor/torrc_original /etc/tor/torrc
mkdir -p /home/debian-tor/.tor/keys
chown -R debian-tor:debian-tor /home/debian-tor
gosu debian-tor tor

exec /entrypoint.sh bitcoind
