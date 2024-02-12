#!/usr/bin/env python3

import json
import os
from pathlib import Path

from test_base import TestBase

graph_file_path = Path(os.path.dirname(__file__)) / "data" / "v25_x_12.graphml"

base = TestBase()
base.start_server()
print(base.warcli(f"network start {graph_file_path}"))
base.wait_for_all_tanks_status(target="running")

onion_addr = None


def wait_for_reachability():
    try:
        global onion_addr
        info = json.loads(base.warcli("rpc 0 getnetworkinfo"))
        for net in info["networks"]:
            if net["name"] == "ipv4" and not net["reachable"]:
                return False
            if net["name"] == "onion" and not net["reachable"]:
                return False
        if len(info["localaddresses"]) != 2:
            return False
        for addr in info["localaddresses"]:
            assert "100." in addr["address"] or ".onion" in addr["address"]
            if ".onion" in addr["address"]:
                onion_addr = addr["address"]
                return True
    except Exception:
        return False


print("\nChecking IPv4 and onion reachability")
base.wait_for_predicate(wait_for_reachability, timeout=10 * 60)


print("\nAttempting addnode to onion peer")
base.warcli(f"rpc 1 addnode {onion_addr} add")


def wait_for_onion_peer():
    peers = json.loads(base.warcli("rpc 0 getpeerinfo"))
    for peer in peers:
        print(f"Waiting for one onion peer: {peer['network']} {peer['addr']}")
        if peer["network"] == "onion":
            return True
    return False


# Might take up to 10 minutes
base.wait_for_predicate(wait_for_onion_peer, timeout=10 * 60)

base.stop_server()
