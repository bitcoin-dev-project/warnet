#!/bin/bash

RPC_USER="warnet_user"
RPC_PASS="2themoon"
WALLET_NAME="miner"

# Function to generate a random number between min and max (inclusive)
random_range() {
  local min=$1
  local max=$2
  echo $((RANDOM % (max - min + 1) + min))
}

# Function to get a random element from an array
random_choice() {
  local arr=("$@")
  echo "${arr[RANDOM % ${#arr[@]}]}"
}

# Create an array of addresses
create_addresses() {
  local address_types=("legacy" "p2sh-segwit" "bech32" "bech32m")
  local addresses=()
  for type in "${address_types[@]}"; do
    local new_address
    new_address=$(bitcoin-cli -regtest -rpcuser="$RPC_USER" -rpcpassword="$RPC_PASS" -rpcwallet="$WALLET_NAME" getnewaddress "" "$type")
    addresses+=("$new_address")
  done
  printf '%s\n' "${addresses[@]}"
}

# Main loop
main() {
  # Check if wallet exists, create if it doesn't
  if ! bitcoin-cli -regtest -rpcuser="$RPC_USER" -rpcpassword="$RPC_PASS" listwallets | grep -q "$WALLET_NAME"; then
    bitcoin-cli -regtest -rpcuser="$RPC_USER" -rpcpassword="$RPC_PASS" createwallet "$WALLET_NAME"
  fi

  # Use mapfile to read the addresses into an array
  local addresses
  mapfile -t addresses < <(create_addresses)
  echo "Got addresses ${addresses[*]}"
  bitcoin-cli -regtest -rpcwallet="$WALLET_NAME" generatetoaddress 110 "${addresses[3]}"
  local interval=1

  while true; do
    # Get balance
    balance=$(bitcoin-cli -regtest -rpcuser="$RPC_USER" -rpcpassword="$RPC_PASS" -rpcwallet="$WALLET_NAME" getbalance)
    echo "Current balance: $balance"
    if (( $(echo "$balance < 1" | bc -l) )); then
      bitcoin-cli -regtest -rpcuser="$RPC_USER" -rpcpassword="$RPC_PASS" -rpcwallet="$WALLET_NAME" generatetoaddress 110 "${addresses[3]}"
      sleep "$interval"
      continue
    fi

    # Determine number of outputs
    num_out=$(random_range 1 $((${#addresses[@]} / 2)))

    # Prepare amounts
    amounts=""
    for ((i = 0; i < num_out; i++)); do
      sats=$(echo "scale=0; ($balance / 20 / $num_out) * 100000000" | bc)
      amount=$(echo "scale=8; $(random_range $((sats / 4)) "$sats") / 100000000" | bc)
      address=$(random_choice "${addresses[@]}")
      amounts+="\"$address\":$amount,"
    done
    amounts=${amounts%,} # Remove trailing comma

    # Send transaction
    tx_id=$(bitcoin-cli -regtest -rpcuser="$RPC_USER" -rpcpassword="$RPC_PASS" -rpcwallet="$WALLET_NAME" sendmany "" "{$amounts}")

    echo "Sent transaction with $num_out outputs. Transaction ID: $tx_id"

    sleep "$interval"
  done
}

main
