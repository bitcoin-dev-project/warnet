#!/bin/bash
# Custom warnet entrypoint instructions, will be run before base image entrypoint.sh

# bitcoin
usermod -a -G debian-tor bitcoin

# tor
mkdir -p /home/debian-tor/.tor/keys
chown -R debian-tor:debian-tor /home/debian-tor
chown -R debian-tor:debian-tor /etc/tor
gosu debian-tor tor

exec /entrypoint.sh bitcoind
