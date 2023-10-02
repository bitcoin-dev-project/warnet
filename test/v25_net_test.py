#!/usr/bin/env python3

import json
import os
from test_base import TestBase
from pathlib import Path

graph_file_path = Path(os.path.dirname(__file__)) / "data" / "v25_x_12.graphml"

base = TestBase()
base.start_server()
print(base.warcli(f"network start {graph_file_path}"))
base.wait_for_all_tanks_status(target="running")

onion_addr = None

print("\nChecking IPv4 and onion reachability")
info = json.loads(base.warcli("rpc 0 getnetworkinfo"))
for net in info["networks"]:
    if net["name"] == "ipv4":
        assert net["reachable"]
    if net["name"] == "onion":
        assert net["reachable"]
assert len(info["localaddresses"]) == 2
for addr in info["localaddresses"]:
    assert "100." in addr["address"] or ".onion" in addr["address"]
    if ".onion" in addr["address"]:
        onion_addr = addr["address"]

print("\nAttempting addnode to onion peer")
base.warcli(f"rpc 1 addnode --params={onion_addr} --params=add")
def wait_for_onion_peer():
    peers = json.loads(base.warcli("rpc 0 getpeerinfo"))
    for peer in peers:
        print(f"Waiting for one onion peer: {peer['network']} {peer['addr']}")
        if peer["network"] == "onion":
            return True
    return False
# Might take up to 10 minutes
base.wait_for_predicate(wait_for_onion_peer, timeout=10*60)

base.stop_server()
