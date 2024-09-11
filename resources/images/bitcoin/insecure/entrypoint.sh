#!/usr/bin/env bash
set -e

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

# Conditionally add -printtoconsole for Bitcoin version 0.16.1
if [ "${BITCOIN_VERSION}" == "0.16.1" ]; then
  exec "$@" -printtoconsole
else
  exec "$@"
fi
