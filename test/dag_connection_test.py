#!/usr/bin/env python3

import os
import time
from pathlib import Path

from test_base import TestBase

graph_file_path = Path(os.path.dirname(__file__)) / "data" / "ten_semi_unconnected.graphml"

base = TestBase()

base.start_server()
print(base.warcli(f"network start {graph_file_path}"))
base.wait_for_all_tanks_status(target="running")
base.wait_for_all_edges()

# Start scenario
base.warcli(f"scenarios run connect_dag --network_name={base.network_name}")

counter = 0
seconds = 180
while (len(base.rpc("scenarios_list_running")) == 1
       and base.rpc("scenarios_list_running")[0]["active"]):
    time.sleep(1)
    counter += 1
    if counter > seconds:
        pid = base.rpc("scenarios_list_running")[0]['pid']
        base.warcli(f"scenarios stop {pid}", False)
        print(f"{os.path.basename(__file__)} more than {seconds} seconds")
        assert counter < seconds

base.stop_server()
