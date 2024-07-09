#!/usr/bin/env python3

import os
import time
from pathlib import Path

from test_base import TestBase


class DAGConnectionTest(TestBase):
    def __init__(self):
        super().__init__()
        self.graph_file_path = (
            Path(os.path.dirname(__file__)) / "data" / "ten_semi_unconnected.graphml"
        )
        self.scenario_timeout = 180  # seconds

    def run_test(self):
        self.start_server()
        try:
            self.setup_network()
            self.run_connect_dag_scenario()
        finally:
            self.stop_server()

    def setup_network(self):
        self.log.info("Setting up network")
        self.log.info(self.warcli(f"network start {self.graph_file_path}"))
        self.wait_for_all_tanks_status(target="running")
        self.wait_for_all_edges()

    def run_connect_dag_scenario(self):
        self.log.info("Running connect_dag scenario")
        self.warcli("scenarios run-file test/framework_tests/connect_dag.py")

        start_time = time.time()
        while time.time() - start_time < self.scenario_timeout:
            running_scenarios = self.rpc("scenarios_list_running")
            if not running_scenarios:
                self.log.info("Scenario completed successfully")
                return

            if len(running_scenarios) == 1 and not running_scenarios[0]["active"]:
                self.log.info("Scenario completed successfully")
                return

            time.sleep(1)

        self.log.error(f"Scenario did not complete within {self.scenario_timeout} seconds")
        self.stop_running_scenario()
        raise AssertionError(f"Scenario timed out after {self.scenario_timeout} seconds")

    def stop_running_scenario(self):
        running_scenarios = self.rpc("scenarios_list_running")
        if running_scenarios:
            pid = running_scenarios[0]["pid"]
            self.log.warning(f"Stopping scenario with PID {pid}")
            self.warcli(f"scenarios stop {pid}", False)


if __name__ == "__main__":
    test = DAGConnectionTest()
    test.run_test()
