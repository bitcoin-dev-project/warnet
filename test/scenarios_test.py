#!/usr/bin/env python3

import os
from pathlib import Path

from test_base import TestBase

from warnet.k8s import delete_pod
from warnet.process import run_command
from warnet.scenarios import _active as scenarios_active


class ScenariosTest(TestBase):
    def __init__(self):
        super().__init__()
        self.network_dir = Path(os.path.dirname(__file__)) / "data" / "12_node_ring"

    def run_test(self):
        try:
            self.setup_network()
            self.test_scenarios()
        finally:
            self.stop_server()

    def setup_network(self):
        self.log.info("Setting up network")
        self.log.info(self.warnet(f"deploy {self.network_dir}"))
        self.wait_for_all_tanks_status(target="running")
        self.wait_for_all_edges()

    def test_scenarios(self):
        self.run_and_check_miner_scenario_from_file()
        self.run_and_check_scenario_from_file()

    def scenario_running(self, scenario_name: str):
        """Check that we are only running a single scenario of the correct name"""
        active = scenarios_active()
        assert len(active) == 1
        return scenario_name in active[0]["commander"]

    def run_and_check_scenario_from_file(self):
        scenario_file = "test/data/scenario_p2p_interface.py"

        def check_scenario_clean_exit():
            active = scenarios_active()
            assert len(active) == 1
            return active[0]["status"] == "succeeded"

        self.log.info(f"Running scenario from: {scenario_file}")
        self.warnet(f"run {scenario_file}")
        self.wait_for_predicate(lambda: check_scenario_clean_exit())

    def run_and_check_miner_scenario_from_file(self):
        scenario_file = "resources/scenarios/miner_std.py"
        self.log.info(f"Running scenario from file: {scenario_file}")
        self.warnet(f"run {scenario_file} --allnodes --interval=1")
        start = int(self.warnet("bitcoin rpc tank-0000 getblockcount"))
        self.wait_for_predicate(lambda: self.scenario_running("commander-minerstd"))
        self.wait_for_predicate(lambda: self.check_blocks(2, start=start))
        self.stop_scenario()

    def check_blocks(self, target_blocks, start: int = 0):
        count = int(self.warnet("bitcoin rpc tank-0000 getblockcount"))
        self.log.debug(f"Current block count: {count}, target: {start + target_blocks}")

        try:
            active = scenarios_active()
            commander = active[0]["commander"]
            command = f"kubectl logs {commander}"
            print("\ncommander output:")
            print(run_command(command))
            print("\n")
        except Exception:
            pass

        return count >= start + target_blocks

    def stop_scenario(self):
        self.log.info("Stopping running scenario")
        running = scenarios_active()
        assert len(running) == 1, f"Expected one running scenario, got {len(running)}"
        assert running[0]["status"] == "running", "Scenario should be running"
        delete_pod(running[0]["commander"])
        self.wait_for_predicate(self.check_scenario_stopped)

    def check_scenario_stopped(self):
        running = scenarios_active()
        self.log.debug(f"Checking if scenario stopped. Running scenarios: {len(running)}")
        return len(running) == 0


if __name__ == "__main__":
    test = ScenariosTest()
    test.run_test()
