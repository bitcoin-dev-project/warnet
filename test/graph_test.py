#!/usr/bin/env python3

import json
import os
import tempfile
import uuid
from pathlib import Path

from test_base import TestBase
from warnet.utils import DEFAULT_TAG, channel_match

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
print(base.warcli(f"graph import-json {json_file_path} --outfile={tf_import}", network=False))
base.wait_for_predicate(lambda: Path(tf_import).exists())

# Validate the graph schema
assert "invalid" not in base.warcli(f"graph validate {Path(tf_create)}", False)
assert "invalid" not in base.warcli(f"graph validate {Path(tf_import)}", False)

# Test that the graphs actually work... now we need a server
base.start_server()

print("\nTesting created graph...")
print(base.warcli(f"network start {Path(tf_create)}"))
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

print("Ensuring warnet LN channel policies match imported JSON description")
with open(json_file_path) as file:
    actual = json.loads(base.warcli("lncli 0 describegraph"))["edges"]
    expected = json.loads(file.read())["edges"]
    expected = sorted(expected, key=lambda chan: int(chan['channel_id']))
    for chan_index, actual_chan in enumerate(actual):
        expected_chan = expected[chan_index]
        if not channel_match(actual_chan, expected_chan, allow_flip=True):
            raise Exception(
                f"Channel policy doesn't match source: {actual_chan['channel_id']}\n" +
                "Actual:\n" + json.dumps(actual_chan, indent=2) +
                "Expected:\n" + json.dumps(expected_chan, indent=2)
            )

base.stop_server()
