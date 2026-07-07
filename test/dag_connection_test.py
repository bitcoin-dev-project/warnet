#!/usr/bin/env python3

import json
import os
from pathlib import Path

import yaml
from test_base import TestBase


class DAGConnectionTest(TestBase):
    def __init__(self):
        super().__init__()
        self.network_dir = Path(os.path.dirname(__file__)) / "data" / "ten_semi_unconnected"
        self.scen_dir = Path(os.path.dirname(__file__)).parent / "resources" / "scenarios"

    def run_test(self):
        try:
            self.setup_network()
            self.check_addconnections()
            self.run_connect_dag_scenario()
        finally:
            self.cleanup()

    def setup_network(self):
        self.log.info("Setting up network")
        self.log.info(self.warnet(f"deploy {self.network_dir}"))
        self.log.info("Waiting for pods")
        self.wait_for_all_tanks_status(target="running")
        self.log.info("Waiting for addnode connections")
        self.wait_for_all_edges()

    def check_addconnections(self):
        self.log.info("Waiting for addconnection connections")

        # should match test/data/ten_semi_unconnected/network.yaml
        with open(self.network_dir / "network.yaml") as f:
            all_expected = yaml.safe_load(f)

        all_actual = {
            "tank-0003": json.loads(self.warnet("bitcoin rpc tank-0003 getpeerinfo")),
            "tank-0004": json.loads(self.warnet("bitcoin rpc tank-0004 getpeerinfo")),
            "tank-0005": json.loads(self.warnet("bitcoin rpc tank-0005 getpeerinfo")),
        }

        for node in all_expected["nodes"]:
            tank = node["name"]
            expected = node.get("addconnection", [])
            actual = all_actual.get(tank, {})
            for conn_ex in expected:
                self.log.info(f"Asserting connection: {tank} {conn_ex}")
                assert any(
                    conn_ac["addr"] == conn_ex["to"]
                    and conn_ac["connection_type"] == (conn_ex.get("type", "outbound-full-relay"))
                    and conn_ac["transport_protocol_type"]
                    == ("v1" if "v2" in conn_ex and not conn_ex["v2"] else "v2")
                    for conn_ac in actual
                ), f"\nactual: {actual}\nexpected: {expected}"

    def run_connect_dag_scenario(self):
        scenario_file = self.scen_dir / "test_scenarios" / "connect_dag.py"
        self.log.info(f"Running scenario from: {scenario_file}")
        self.warnet(f"run {scenario_file} --source_dir={self.scen_dir}")
        self.wait_for_all_scenarios()


if __name__ == "__main__":
    test = DAGConnectionTest()
    test.run_test()
