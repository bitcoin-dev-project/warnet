#!/usr/bin/env python3
import tempfile
import uuid
from pathlib import Path
from test_base import TestBase
from warnet.utils import DEFAULT_TAG

base = TestBase()
base.network = False
base.start_server()

with tempfile.TemporaryDirectory() as dir:
    tf = f"{dir}/{str(uuid.uuid4())}.graphml"
    print(f"Writing test graph to {tf}")
    print(base.warcli(f"graph create n=10 --outfile={tf} --version={DEFAULT_TAG}", network=False))
    base.wait_for_predicate(lambda: Path(tf).exists())

    # Test that the graph actually works
    print(base.warcli(f"network start {Path(tf)}"))
    base.wait_for_all_tanks_status(target="running")
    base.warcli("rpc 0 getblockcount")

base.stop_server()
