#!/usr/bin/env python3

import os
from pathlib import Path

from test_base import TestBase


class ScenariosTest(TestBase):
    def __init__(self):
        super().__init__()
        self.graph_file_path = Path(os.path.dirname(__file__)) / "data" / "12_node_ring.graphml"

    def run_test(self):
        try:
            self.start_server()
            self.setup_network()
            self.test_scenarios()
        finally:
            self.stop_server()

    def setup_network(self):
        self.log.info("Setting up network")
        self.log.info(self.warcli(f"network start {self.graph_file_path}"))
        self.wait_for_all_tanks_status(target="running")

    def test_scenarios(self):
        self.check_available_scenarios()
        self.run_and_check_scenario("miner_std")
        self.run_and_check_scenario_from_file("src/warnet/scenarios/miner_std.py")

    def check_available_scenarios(self):
        self.log.info("Checking available scenarios")
        # Use rpc instead of warcli so we get raw JSON object
        scenarios = self.rpc("scenarios_available")
        assert len(scenarios) == 4, f"Expected 4 available scenarios, got {len(scenarios)}"
        self.log.info(f"Found {len(scenarios)} available scenarios")

    def scenario_running(self, scenario_name: str):
        """Check that we are only running a single scenario of the correct name"""
        active = self.rpc("scenarios_list_running")
        running = scenario_name in active[0]["cmd"]
        return running and len(active) == 1

    def run_and_check_scenario(self, scenario_name):
        self.log.info(f"Running scenario: {scenario_name}")
        self.warcli(f"scenarios run {scenario_name} --allnodes --interval=1")
        self.wait_for_predicate(lambda: self.scenario_running(scenario_name))
        self.wait_for_predicate(lambda: self.check_blocks(30))
        self.stop_scenario()

    def run_and_check_scenario_from_file(self, scenario_file):
        self.log.info(f"Running scenario from file: {scenario_file}")
        self.warcli(f"scenarios run-file {scenario_file} --allnodes --interval=1")
        start = int(self.warcli("bitcoin rpc 0 getblockcount"))
        scenario_name = os.path.splitext(os.path.basename(scenario_file))[0]
        self.wait_for_predicate(lambda: self.scenario_running(scenario_name))
        self.wait_for_predicate(lambda: self.check_blocks(2, start=start))
        self.stop_scenario()

    def check_blocks(self, target_blocks, start: int = 0):
        running = self.rpc("scenarios_list_running")
        assert len(running) == 1, f"Expected one running scenario, got {len(running)}"
        assert running[0]["active"], "Scenario should be active"

        count = int(self.warcli("bitcoin rpc 0 getblockcount"))
        self.log.debug(f"Current block count: {count}, target: {start + target_blocks}")
        return count >= start + target_blocks

    def stop_scenario(self):
        self.log.info("Stopping running scenario")
        running = self.rpc("scenarios_list_running")
        assert len(running) == 1, f"Expected one running scenario, got {len(running)}"
        assert running[0]["active"], "Scenario should be active"
        self.warcli(f"scenarios stop {running[0]['pid']}", False)
        self.wait_for_predicate(self.check_scenario_stopped)

    def check_scenario_stopped(self):
        running = self.rpc("scenarios_list_running")
        self.log.debug(f"Checking if scenario stopped. Running scenarios: {len(running)}")
        return len(running) == 0


if __name__ == "__main__":
    test = ScenariosTest()
    test.run_test()
