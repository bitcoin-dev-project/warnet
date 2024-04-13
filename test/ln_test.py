#!/usr/bin/env python3

import json
import os
from pathlib import Path

from backends import ServiceType
from test_base import TestBase

graph_file_path = Path(os.path.dirname(__file__)) / "data" / "ln.graphml"

base = TestBase()
base.start_server()


def get_cb_forwards(index):
    cmd = "wget -q -O - 127.0.0.1:9235/api/forwarding_history"
    res = base.wait_for_rpc(
        "exec_run", [index, ServiceType.CIRCUITBREAKER.value, cmd, base.network_name]
    )
    return json.loads(res)


print(base.warcli(f"network start {graph_file_path}"))
base.wait_for_all_tanks_status(target="running")
base.wait_for_all_edges()

print("\nRunning LN Init scenario")
base.warcli("rpc 0 getblockcount")
base.warcli("scenarios run ln_init")
base.wait_for_all_scenarios()

node2pub, node2host = json.loads(base.warcli(f"lncli 2 getinfo"))["uris"][0].split("@")

print("\nEnsuring node-level channel policy settings")
chan_id = json.loads(base.warcli("lncli 2 listchannels"))["channels"][0]["chan_id"]
chan = json.loads(base.warcli(f"lncli 2 getchaninfo {chan_id}"))
# node_1 or node_2 is tank 2 with its non-default --bitcoin.timelockdelta=33
if chan["node1_policy"]["time_lock_delta"] != 33:
    assert chan["node2_policy"]["time_lock_delta"] == 33

print("\nEnsuring no circuit breaker forwards yet")
assert len(get_cb_forwards(1)["forwards"]) == 0

print("\nTest LN payment from 0 -> 2")
inv = json.loads(base.warcli("lncli 2 addinvoice --amt=2000"))["payment_request"]

print(f"\nGot invoice from node 2: {inv}")
print("\nPaying invoice from node 0...")
print(base.warcli(f"lncli 0 payinvoice -f {inv}"))

print("Waiting for payment success")
def check_invoices():
    invs = json.loads(base.warcli("lncli 2 listinvoices"))["invoices"]
    if len(invs) > 0 and invs[0]["state"] == "SETTLED":
        print("\nSettled!")
        return True
    else:
        return False
base.wait_for_predicate(check_invoices)

print("\nEnsuring channel-level channel policy settings: source")
payment = json.loads(base.warcli("lncli 0 listpayments"))["payments"][0]
assert payment["fee_msat"] == "5506"

print("\nEnsuring circuit breaker tracked payment")
assert len(get_cb_forwards(1)["forwards"]) == 1

print("\nTest LN payment from 2 -> 0")
inv = json.loads(base.warcli("lncli 0 addinvoice --amt=1000"))["payment_request"]

print(f"\nGot invoice from node 0: {inv}")
print("\nPaying invoice from node 2...")
print(base.warcli(f"lncli 2 payinvoice -f {inv}"))

print("Waiting for payment success")
def check_invoices(index):
    invs = json.loads(base.warcli(f"lncli {index} listinvoices"))["invoices"]
    settled = 0
    for inv in invs:
        if inv["state"] == "SETTLED":
            settled += 1
    return settled
base.wait_for_predicate(lambda: check_invoices(0) == 1)

print("\nEnsuring channel-level channel policy settings: target")
payment = json.loads(base.warcli("lncli 2 listpayments"))["payments"][0]
assert payment["fee_msat"] == "2213"

print("\nEngaging simln")
activity = [{
  "source": "ln-0",
  "destination": node2pub,
  "interval_secs": 1,
  "amount_msat": 2000
}]
base.warcli(f"network export --exclude=[1] --activity={json.dumps(activity).replace(' ', '')}")
base.wait_for_predicate(lambda: check_invoices(2) > 1)
assert check_invoices(0) == 1
assert check_invoices(1) == 0

base.stop_server()
