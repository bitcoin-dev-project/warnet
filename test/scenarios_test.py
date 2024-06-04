#!/usr/bin/env python3

import os
from pathlib import Path

from test_base import TestBase

graph_file_path = Path(os.path.dirname(__file__)) / "data" / "v25_x_12.graphml"

base = TestBase()
base.start_server()
print(base.warcli(f"network start {graph_file_path}"))
base.wait_for_all_tanks_status(target="running")

# Use rpc instead of warcli so we get raw JSON object
scenarios = base.rpc("scenarios_available")
assert len(scenarios) == 5

# Start scenario
base.warcli("scenarios run miner_std --allnodes --interval=1")


def check_blocks():
    # Ensure the scenario is still working
    running = base.rpc("scenarios_list_running")
    assert len(running) == 1
    assert running[0]["active"]
    assert "miner_std" in running[0]["cmd"]

    count = int(base.warcli("rpc 0 getblockcount"))
    print(f"Waiting for 30 blocks: {count}")
    return count >= 30


base.wait_for_predicate(check_blocks)

# Stop scenario
running = base.rpc("scenarios_list_running")
assert len(running) == 1
assert running[0]["active"]
base.warcli(f"scenarios stop {running[0]['pid']}", False)


def check_stop():
    running = base.rpc("scenarios_list_running")
    print(f"Waiting for scenario to stop: {running}")
    return len(running) == 0


base.wait_for_predicate(check_stop)

base.stop_server()
