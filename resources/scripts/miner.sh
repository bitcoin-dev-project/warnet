#!/bin/bash

# Generate a Poisson-distributed sleep time between 1 and 20 seconds
generate_poisson_sleep() {
  local lambda=10 # Average rate (lambda) for Poisson distribution
  local sleep_time
  sleep_time=$(awk -v lambda="$lambda" 'BEGIN {
    sum = 0;
    while (sum <= lambda) {
      sum += -log(1 - rand());
    }
    print int(sum);
  }')

  # Ensure sleep time is between 1 and 20 seconds
  if [ "$sleep_time" -lt 1 ]; then
    sleep_time=1
  elif [ "$sleep_time" -gt 20 ]; then
    sleep_time=20
  fi

  echo "$sleep_time"
}

echo "Running miner role with Poisson-distributed sleep between blocks"

echo "Creating a new wallet called \"miner\""
bitcoin-cli -regtest -rpcuser=warnet_user -rpcpassword=2themoon createwallet "miner"
sleep "$(generate_poisson_sleep)"

echo "Beginning mining process"
while true; do
  bitcoin-cli -regtest -rpcuser=warnet_user -rpcpassword=2themoon -generate 1
  sleep "$(generate_poisson_sleep)"
done
