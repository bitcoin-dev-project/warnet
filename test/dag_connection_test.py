#!/usr/bin/env python3

import os
from pathlib import Path

from test_base import TestBase


class DAGConnectionTest(TestBase):
    def __init__(self):
        super().__init__()
        self.network_dir = Path(os.path.dirname(__file__)) / "data" / "ten_semi_unconnected"
        self.scen_dir = Path(os.path.dirname(__file__)).parent / "resources" / "scenarios"

    def run_test(self):
        try:
            self.setup_network()
            self.run_connect_dag_scenario()
        finally:
            self.cleanup()

    def setup_network(self):
        self.log.info("Setting up network")
        self.log.info(self.warnet(f"deploy {self.network_dir}"))
        self.wait_for_all_tanks_status(target="running")
        self.wait_for_all_edges()

    def run_connect_dag_scenario(self):
        scenario_file = self.scen_dir / "test_scenarios" / "connect_dag.py"
        self.log.info(f"Running scenario from: {scenario_file}")
        self.warnet(f"run {scenario_file} --source_dir={self.scen_dir}")
        self.wait_for_all_scenarios()


if __name__ == "__main__":
    test = DAGConnectionTest()
    test.run_test()
