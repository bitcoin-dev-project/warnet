#!/usr/bin/env python3

import json
import os
import tempfile
import uuid
from pathlib import Path

import requests
from test_base import TestBase
from warnet.utils import DEFAULT_TAG, channel_match

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
print(base.warcli(f"graph import-json {json_file_path} --outfile={tf_import} --ln_image=carlakirkcohen/lnd:attackathon --cb=pinheadmz/circuitbreaker:278737d", network=False))
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

if base.backend == "compose":
    cadvisor_res = requests.get("http://localhost:23000/api/v1.1/subcontainers")
    assert cadvisor_res.status_code == 200
    ok = False
    for c in cadvisor_res.json():
        if "aliases" in c and f"{base.network_name}-tank-bitcoin-000000" in c["aliases"]:
            ok = True
            break
    if ok:
        print("cadvisor OK")
    else:
        raise Exception("cadvisor not OK")

    fo_res = requests.get("http://localhost:23001/api/networks.json")
    assert fo_res.status_code == 200
    network_id = fo_res.json()["networks"][0]["id"]
    fo_data = requests.get(f"http://localhost:23001/api/{network_id}/data.json")
    assert fo_data.status_code == 200
    node = fo_data.json()["nodes"][0]
    if node["description"] == "Warnet tank 0":
        print("forkobserver OK")
    else:
        raise Exception("forkobserver not OK")

    grafana_res = requests.get("http://localhost:23002/api/datasources/uid/prometheusdatasource/health")
    assert grafana_res.status_code == 200
    health = grafana_res.json()
    if health["message"] == "Successfully queried the Prometheus API.":
        print("grafana & prometheus OK")
    else:
        raise Exception("grafana & prometheus not OK")

    # quick checks on the data sources
    nodex_res = requests.get("http://localhost:23003")
    if nodex_res.status_code == 200:
        print("nodeexporter OK")
    else:
        raise Exception("nodeexporter not OK")
    prom_res = requests.get("http://localhost:23004")
    if prom_res.status_code == 200:
        print("prometheus OK")
    else:
        raise Exception("prometheus not OK")

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
