#!/usr/bin/env python3

import json
import os
from test_base import TestBase
from pathlib import Path

graph_file_path = Path(os.path.dirname(__file__)) / "data" / "build_v24_test.graphml"

base = TestBase()
base.start_server()
print(base.warcli(f"network start {graph_file_path}"))
base.wait_for_all_tanks_status(target="running")

print("\nWait for p2p connections")
def check_peers():
    info0 = json.loads(base.warcli("rpc 0 getpeerinfo"))
    info1 = json.loads(base.warcli("rpc 1 getpeerinfo"))
    print(f"Waiting for both nodes to get one peer: node0: {len(info0)}, node1: {len(info1)}")
    return len(info0) == 1 and len(info1) == 1
base.wait_for_predicate(check_peers)

base.stop_server()
