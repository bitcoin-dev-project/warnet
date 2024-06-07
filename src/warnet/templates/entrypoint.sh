#!/bin/bash
set -e

# Only run this tor section if the TOR=1 env var is set
if [ "${TOR:-0}" -eq 1 ]; then

    # Add bitcoin user to tor group to read the auth cookie
    usermod -a -G debian-tor bitcoin

    # ===========Tor setup===========
    # Use custom torrc for warnet
    if [ "${WARNET:-0}" -eq 1 ]; then
        mv /etc/tor/warnet-torrc /etc/tor/torrc
    fi
    echo "Address $(ip addr show eth0 | grep "inet\b" | awk '{print $2}' | cut -d/ -f1)" >> /etc/tor/torrc
    mkdir -p /home/debian-tor/.tor/keys
    chown -R debian-tor:debian-tor /home/debian-tor
    # Start tor in the background
    su-exec debian-tor:debian-tor tor &
    # ===============================
fi

if [ "$(echo "$1" | cut -c1)" = "-" ]; then
  echo "$0: assuming arguments for bitcoind"

  set -- bitcoind "$@"
fi

if [ "$(echo "$1" | cut -c1)" = "-" ] || [ "$1" = "bitcoind" ]; then
  mkdir -p "$BITCOIN_DATA"
  chmod 700 "$BITCOIN_DATA"
  echo "$0: setting data directory to $BITCOIN_DATA"
  set -- "$@" -datadir="$BITCOIN_DATA"
fi

# Incorporate additional arguments for bitcoind if BITCOIN_ARGS is set.
if [ -n "$BITCOIN_ARGS" ]; then
  IFS=' ' read -ra ARG_ARRAY <<< "$BITCOIN_ARGS"
  set -- "$@" "${ARG_ARRAY[@]}"
fi

echo
exec "$@"
