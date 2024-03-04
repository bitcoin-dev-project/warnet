#!/usr/bin/env python3

import os
from pathlib import Path

from test_base import TestBase

graph_file_path = Path(os.path.dirname(__file__)) / "data" / "v25_x_12.graphml"

base = TestBase()
base.start_server()
print(base.warcli(f"network start {graph_file_path}"))
base.wait_for_all_tanks_status(target="running")
base.wait_for_all_edges()

# Exponential backoff will repeat this command until it succeeds.
# That's when we are ready for commands
base.warcli("rpc 0 getblockcount")

# Fund wallet
base.warcli("rpc 1 createwallet miner")
base.warcli("rpc 1 -generate 101")

base.wait_for_predicate(lambda: "101" in base.warcli("rpc 0 getblockcount"))

txid = base.warcli(
    "rpc 1 sendtoaddress bcrt1qthmht0k2qnh3wy7336z05lu2km7emzfpm3wg46 0.1"
)

base.wait_for_predicate(lambda: txid in base.warcli("rpc 0 getrawmempool"))

node_log = base.warcli("debug-log 1")
assert txid in node_log

all_logs = base.warcli(f"grep-logs {txid}")
count = all_logs.count("Enqueuing TransactionAddedToMempool")
# should be at least more than one node
assert count > 1

msgs = base.warcli("messages 0 1")
assert "verack" in msgs

base.stop_server()
