#!/usr/bin/env python3

import json
import os
import sys
from pathlib import Path

from test_base import TestBase

graph_file_path = Path(os.path.dirname(__file__)) / "data" / "onion.graphml"

base = TestBase()

if base.backend != "compose":
    sys.exit(1)

base.start_server()

print(base.warcli(f"network start {graph_file_path}"))
base.wait_for_all_tanks_status(target="running")

status = base.rpc("network_status", {"network": base.network_name})
num_tanks = len(status)

base.warcli("rpc 0 getblockcount")

print("\nRunning Onion Init scenario")
base.warcli("scenarios run onion_init")
base.wait_for_all_scenarios()

def one_peer_each():
    counts = []
    total = 0
    for i in range(num_tanks):
        try:
            info = base.rpc("tank_bcli", [i, "getpeerinfo", [], base.network_name])
            count = len(json.loads(info))
            counts.append(count)
            total += count
        except Exception as e:
            print(f"rpc getpeerinfo error from tank {i}: {e}")
            return False
    print(f"Total connections: {total}")
    print(f"Connections by tank: {counts}")
    return total >= num_tanks // 2
base.wait_for_predicate(one_peer_each, timeout=20*60)

for i in range(num_tanks):
    print(base.warcli(f"rpc {i} -netinfo 4"))

base.stop_server()
