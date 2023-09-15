#!/bin/bash
set -e

# Add bitcoin user to tor group to read the auth cookie
usermod -a -G debian-tor bitcoin
echo "Address $(ip addr show eth0 | grep "inet\b" | awk '{print $2}' | cut -d/ -f1)" >> /etc/tor/torrc
mkdir -p /home/debian-tor/.tor/keys
chown -R debian-tor:debian-tor /home/debian-tor
# Start tor in the background
gosu debian-tor tor &

if [ -n "${UID+x}" ] && [ "${UID}" != "0" ]; then
  usermod -u "$UID" bitcoin
fi

if [ -n "${GID+x}" ] && [ "${GID}" != "0" ]; then
  groupmod -g "$GID" bitcoin
fi

echo "$0: assuming uid:gid for bitcoin:bitcoin of $(id -u bitcoin):$(id -g bitcoin)"

if [ "$(echo "$1" | cut -c1)" = "-" ]; then
  echo "$0: assuming arguments for bitcoind"

  set -- bitcoind "$@"
fi

if [ "$(echo "$1" | cut -c1)" = "-" ] || [ "$1" = "bitcoind" ]; then
  mkdir -p "$BITCOIN_DATA"
  chmod 700 "$BITCOIN_DATA"
  # Fix permissions for home dir.
  chown -R bitcoin:bitcoin "$(getent passwd bitcoin | cut -d: -f6)"
  # Fix permissions for bitcoin data dir.
  chown -R bitcoin:bitcoin "$BITCOIN_DATA"

  echo "$0: setting data directory to $BITCOIN_DATA"

  set -- "$@" -datadir="$BITCOIN_DATA"
fi

# Wait for the dns-seed to start returning results
./check_dns.sh

if [ "$1" = "bitcoind" ] || [ "$1" = "bitcoin-cli" ] || [ "$1" = "bitcoin-tx" ]; then
  echo
  exec gosu bitcoin "$@"
fi

echo
exec "$@"
