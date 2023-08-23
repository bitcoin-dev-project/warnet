#!/bin/bash

open_channel() {
    if [ $# -gt 4 ]; then
        return 1
    fi
    
    local pubkey="$1"
    local amount="$2"
    local ip="$3"
    local port="$4"
    
    local lncli_output=$(lncli --network=regtest openchannel --connect="$ip:$port" --node_key="$pubkey" --local_amt="$amount")
    local funding_txid=$(echo "$lncli_output" | jq -r '.funding_txid')
    echo "$funding_txid"

    return 0
}

node_ready() {
    if [ $# -ne 0 ]; then
        return 1
    fi

    if ! command -v jq &> /dev/null; then
        return 1
    fi

    local lncli_output=$(lncli --network=regtest getinfo)

    synced_to_graph=$(echo "$lncli_output" | jq -r '.synced_to_graph')
    if [ "$synced_to_graph_value" = "false" ]; then
        return 1
    fi

    introduction_pubkey=$(echo "$lncli_output" | jq -r '.identity_pubkey')
    echo $introduction_pubkey

    return 0
}

channel_ready() {
    if [ $# -ne 1 ]; then
        return 1
    fi

    local funding_txid="$1"
    local lncli_output=$(lncli --network=regtest listchannels)

    if [[ $lncli_output =~ "$funding_txid" ]]; then
        return 0
    else
        return 1
    fi
}
