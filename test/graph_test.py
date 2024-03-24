#!/usr/bin/env python3
import tempfile
import uuid
from pathlib import Path

from test_base import TestBase
from warnet.utils import DEFAULT_TAG

base = TestBase()

# Does not require a running Warnet RPC server yet
test_dir = tempfile.TemporaryDirectory()
tf = f"{test_dir.name}/{str(uuid.uuid4())}.graphml"

print(f"CLI tool writing test graph directly to {tf}")
print(base.warcli(f"graph create 10 --outfile={tf} --version={DEFAULT_TAG}", network=False))
base.wait_for_predicate(lambda: Path(tf).exists())

# Validate the graph schema
assert "invalid" not in base.warcli(f"graph validate {Path(tf)}", False)
print(f"Graph at {tf} validated successfully")

# Test that the graph actually works, now we need a server
base.start_server()
print(base.warcli(f"network start {Path(tf)}"))
base.wait_for_all_tanks_status(target="running")
base.wait_for_all_edges()
base.warcli("rpc 0 getblockcount")
base.stop_server()
