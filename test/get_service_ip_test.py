#!/usr/bin/env python3

import os
import time
from pathlib import Path

from test_base import TestBase

graph_file_path = Path(os.path.dirname(__file__)) / "data" / "permutations.graphml"

base = TestBase()

if base.backend == "k8s":
    base.start_server()
    print(base.warcli(f"network start {graph_file_path}"))
    base.wait_for_all_tanks_status(target="running")
    base.wait_for_all_edges()

    # Start scenario
    base.warcli(f"scenarios run get_service_ip --network_name={base.network_name}")

    counter = 0
    while (len(base.rpc("scenarios_list_running")) == 1
           and base.rpc("scenarios_list_running")[0]["active"]):
        time.sleep(1)
        counter += 1
        if counter > 30:
            pid = base.rpc("scenarios_list_running")[0]['pid']
            base.warcli(f"scenarios stop {pid}", False)
            assert counter < 30
else:
    print(f"get_service_ip_test does not test {base.backend}")
    
base.stop_server()
