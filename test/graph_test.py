#!/usr/bin/env python3

import json
import os
import tempfile
import uuid
from pathlib import Path

from test_base import TestBase
from warnet.utils import DEFAULT_TAG

graph_file_path = Path(os.path.dirname(__file__)) / "data" / "services.graphml"
json_file_path = Path(os.path.dirname(__file__)) / "data" / "LN_10.json"
NUM_IMPORTED_NODES = 10

base = TestBase()

# Does not require a running Warnet RPC server yet
test_dir = tempfile.TemporaryDirectory()
tf_create = f"{test_dir.name}/{str(uuid.uuid4())}.graphml"
tf_import = f"{test_dir.name}/{str(uuid.uuid4())}.graphml"

print(f"\nCLI tool creating test graph file: {tf_create}")
print(base.warcli(f"graph create 10 --outfile={tf_create} --version={DEFAULT_TAG}", network=False))
base.wait_for_predicate(lambda: Path(tf_create).exists())

print(f"\nCLI tool importing json and writing test graph file: {tf_import}")
print(
    base.warcli(
        f"graph import-json {json_file_path} --outfile={tf_import} --ln_image=carlakirkcohen/lnd:attackathon --cb=carlakirkcohen/circuitbreaker:attackathon-test",
        network=False,
    )
)
base.wait_for_predicate(lambda: Path(tf_import).exists())

# Validate the graph schema
assert "invalid" not in base.warcli(f"graph validate {Path(tf_create)}", False)
assert "invalid" not in base.warcli(f"graph validate {Path(tf_import)}", False)
assert "invalid" not in base.warcli(f"graph validate {graph_file_path}", False)

# Test that the graphs actually work... now we need a server
base.start_server()


print("\nTesting graph with optional services...")
print(base.warcli(f"network start {graph_file_path}"))
base.wait_for_all_tanks_status(target="running")
base.wait_for_all_edges()
base.warcli("rpc 0 getblockcount")

print("\nChecking services...")
base.warcli("network down")
base.wait_for_all_tanks_status(target="stopped")

print("\nTesting created graph...")
print(base.warcli(f"network start {Path(tf_create)} --force"))
base.wait_for_all_tanks_status(target="running")
base.wait_for_all_edges()
base.warcli("rpc 0 getblockcount")
base.warcli("network down")
base.wait_for_all_tanks_status(target="stopped")

print("\nTesting imported graph...")
print(base.warcli(f"network start {Path(tf_import)} --force"))
base.wait_for_all_tanks_status(target="running")
base.wait_for_all_edges()
base.warcli("rpc 0 getblockcount")
base.warcli("scenarios run ln_init")
base.wait_for_all_scenarios()


def channel_match(ch1, ch2):
    if ch1["capacity"] != ch2["capacity"]:
        return False
    if policy_match(ch1["node1_policy"], ch2["node1_policy"]) and policy_match(
        ch1["node2_policy"], ch2["node2_policy"]
    ):
        return True
    return policy_match(ch1["node1_policy"], ch2["node2_policy"]) and policy_match(
        ch1["node2_policy"], ch2["node1_policy"]
    )


def policy_match(pol1, pol2):
    return (
        max(int(pol1["time_lock_delta"]), 18) == max(int(pol2["time_lock_delta"]), 18)
        and max(int(pol1["min_htlc"]), 1) == max(int(pol2["min_htlc"]), 1)
        and pol1["fee_base_msat"] == pol2["fee_base_msat"]
        and pol1["fee_rate_milli_msat"] == pol2["fee_rate_milli_msat"]
    )


print("Ensuring warnet LN channel policies match imported JSON description")
with open(json_file_path) as file:
    actual = json.loads(base.warcli("lncli 0 describegraph"))["edges"]
    expected = json.loads(file.read())["edges"]
    expected = sorted(expected, key=lambda chan: int(chan["channel_id"]))
    for chan_index, actual_chan in enumerate(actual):
        expected_chan = expected[chan_index]
        if not channel_match(actual_chan, expected_chan):
            raise Exception(
                f"Channel policy doesn't match source: {actual_chan['channel_id']}\n"
                + "Actual:\n"
                + json.dumps(actual_chan, indent=2)
                + "Expected:\n"
                + json.dumps(expected_chan, indent=2)
            )
base.stop_server()
