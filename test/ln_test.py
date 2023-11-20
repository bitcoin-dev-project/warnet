#!/usr/bin/env python3

import json
import os
from time import sleep
from warnet.warnet import Warnet
from test_base import TestBase
from pathlib import Path

graph_file_path = Path(os.path.dirname(__file__)) / "data" / "ln.graphml"

base = TestBase()
base.start_server()
print(base.warcli(f"network start {graph_file_path}"))
base.wait_for_all_tanks_status(target="running")


print("\nTesting warcli network export")
path = Path(base.warcli("network export")) / "sim.json"
with open(path, "r") as file:
    data = json.load(file)
    print(json.dumps(data, indent=4))
    assert len(data["nodes"]) == 3
    for node in data["nodes"]:
        assert os.path.exists(node["macaroon"])
        assert os.path.exists(node["cert"])


print("\nRunning LN Init scenario")
base.warcli("rpc 0 getblockcount")
base.warcli("scenarios run ln_init")
base.wait_for_all_scenarios()


print("\nTest LN payment from 0 -> 2")
wn = Warnet.from_network(base.network_name)
lnd0 = wn.tanks[0].lnnode
lnd2 = wn.tanks[2].lnnode
inv = json.loads(lnd2.lncli("addinvoice --amt=1234"))["payment_request"]

print(f"\nGot invoice from node 2: {inv}")
print("\nPaying invoice from node 0...")
print(lnd0.lncli(f"payinvoice -f {inv}"))

print("Waiting for payment success")
while True:
    invs = json.loads(lnd2.lncli("listinvoices"))["invoices"]
    if len(invs) > 0:
        if invs[0]["state"] == "SETTLED":
            print("\nSettled!")
            break
    sleep(2)

base.stop_server()
