#!/usr/bin/env python3

import os
from pathlib import Path

from test_base import TestBase


class DAGConnectionTest(TestBase):
    def __init__(self):
        super().__init__()
        self.graph_file_path = (
            Path(os.path.dirname(__file__)) / "data" / "ten_semi_unconnected.graphml"
        )

    def run_test(self):
        self.start_server()
        try:
            self.setup_network()
            self.run_connect_dag_scenario()
            self.run_connect_dag_scenario_post_connection()
        finally:
            self.stop_server()

    def setup_network(self):
        self.log.info("Setting up network")
        self.log.info(self.warcli(f"network start {self.graph_file_path}"))
        self.wait_for_all_tanks_status(target="running")
        self.wait_for_all_edges()

    def run_connect_dag_scenario(self):
        self.log.info("Running connect_dag scenario")
        self.log_expected_msgs = [
            "Successfully ran the connect_dag.py scenario using a temporary file"
        ]
        self.log_unexpected_msgs = ["Test failed."]
        self.warcli("scenarios run-file test/framework_tests/connect_dag.py")
        self.wait_for_all_scenarios()
        self.assert_log_msgs()

    def run_connect_dag_scenario_post_connection(self):
        self.log.info("Running connect_dag scenario")
        self.log_expected_msgs = ["Successfully ran the connect_dag.py scenario"]
        self.log_unexpected_msgs = ["Test failed"]
        self.warcli("scenarios run-file test/framework_tests/connect_dag.py")
        self.wait_for_all_scenarios()
        self.assert_log_msgs()


if __name__ == "__main__":
    test = DAGConnectionTest()
    test.run_test()
