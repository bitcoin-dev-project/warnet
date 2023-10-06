#!/usr/bin/env python3

import os
from test_base import TestBase
from pathlib import Path

graph_file_path = Path(os.path.dirname(__file__)) / "data" / "ln.graphml"

base = TestBase()
base.start_server()
print(base.warcli(f"network start {graph_file_path}"))
base.wait_for_all_tanks_status(target="running")

print("\nRunning LN Init scenario")
base.warcli("rpc 0 getblockcount")
base.warcli("scenarios run ln_init")
base.wait_for_all_scenarios()

base.stop_server()
