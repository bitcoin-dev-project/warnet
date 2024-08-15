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

# Function to remove an item from an array
remove_item() {
    local array=("$@")
    unset array[0]
    echo "${array[@]}"
}

# Create an array of addresses
create_addresses() {
    local address_types=("legacy" "p2sh-segwit" "bech32" "bech32m")
    local addresses=()
    for type in "${address_types[@]}"; do
        for i in {1..10}; do
            local new_address
            new_address=$(bitcoin-cli -regtest -rpcuser="$RPC_USER" -rpcpassword="$RPC_PASS" -rpcwallet="$WALLET_NAME" getnewaddress "" "$type")
            addresses+=("$new_address")
        done
    done
    printf '%s\n' "${addresses[@]}"
}

# Prepare amounts with unique addresses
prepare_amounts() {
    local balance=$1
    local num_out=$2
    local addresses=("${@:3}")
    local amounts=""
    local used_addresses=()

    echo "Preparing amounts for transaction:"
    echo "Balance: $balance"
    echo "Number of outputs: $num_out"

    for ((i = 0; i < num_out; i++)); do
        sats=$(echo "scale=0; ($balance / 20 / $num_out) * 100000000" | bc)
        amount=$(echo "scale=8; $(random_range $((sats / 2)) "$sats") / 100000000" | bc)

        # Select a random address that hasn't been used yet
        address=$(random_choice "${addresses[@]}")
        while [[ " ${used_addresses[*]} " =~ " ${address} " ]]; do
            addresses=($(remove_item "${addresses[@]}"))
            address=$(random_choice "${addresses[@]}")
        done

        used_addresses+=("$address")
        amounts+="\"$address\":$amount,"

        echo "Output $((i + 1)):"
        echo "  Address: $address"
        echo "  Sats calculation: ($balance / 2 / $num_out) * 100000000 = $sats"
        echo "  Amount range: $((sats / 2)) to $sats satoshis"
        echo "  Final amount: $amount BTC"
    done

    amounts=${amounts%,} # Remove trailing comma
    echo "Final amounts string: $amounts"
    echo "$amounts"
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
    echo "Created ${#addresses[@]} addresses"
    sleep $((RANDOM % 60 + 1))
    bitcoin-cli -regtest -rpcwallet="$WALLET_NAME" generatetoaddress 101 "${addresses[0]}"
    local interval=1

    while true; do
        # Get balance
        balance=$(bitcoin-cli -regtest -rpcuser="$RPC_USER" -rpcpassword="$RPC_PASS" -rpcwallet="$WALLET_NAME" getbalance)
        echo "Current balance: $balance"
        if (($(echo "$balance < 1" | bc -l))); then
            echo "Balance too low, generating more blocks..."
            sleep $((RANDOM % 60 + 1))
            bitcoin-cli -regtest -rpcuser="$RPC_USER" -rpcpassword="$RPC_PASS" -rpcwallet="$WALLET_NAME" generatetoaddress 101 "${addresses[0]}"
            sleep "$interval"
            continue
        fi

        # Set number of outputs to about 20
        num_out=20

        # Prepare amounts with unique addresses
        amounts=$(prepare_amounts "$balance" "$num_out" "${addresses[@]}")

        echo "Attempting to send transaction..."
        # Send transaction
        tx_id=$(bitcoin-cli -regtest -rpcuser="$RPC_USER" -rpcpassword="$RPC_PASS" -rpcwallet="$WALLET_NAME" sendmany "" "{$amounts}")

        if [ $? -eq 0 ]; then
            echo "Successfully sent transaction with $num_out outputs. Transaction ID: $tx_id"
        else
            echo "Failed to send transaction. Error message:"
            echo "$tx_id"
        fi

        sleep "$interval"
    done
}

main
