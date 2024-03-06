#!/bin/bash
set -e

# Only run this tor section if the TOR=1 env var is set
if [ "${TOR:-0}" -eq 1 ]; then
    # Add our own IP address into Tor configuration file
    echo "Address $(ip addr show eth0 | grep "inet\b" | awk '{print $2}' | cut -d/ -f1)" >> /etc/tor/torrc
    # Start tor in the background as bitcoin user
    su-exec bitcoin:bitcoin tor -f /etc/tor/torrc &
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
