#!/usr/bin/env python3

import os
import re
from pathlib import Path

from test_base import TestBase

from warnet.control import stop_scenario
from warnet.process import run_command
from warnet.status import _get_deployed_scenarios as scenarios_deployed


class ScenariosTest(TestBase):
    def __init__(self):
        super().__init__()
        self.network_dir = Path(os.path.dirname(__file__)) / "data" / "12_node_ring"
        self.scen_dir = Path(os.path.dirname(__file__)).parent / "resources" / "scenarios"

    def run_test(self):
        try:
            self.setup_network()
            self.run_and_check_miner_scenario_from_file()
            self.run_and_check_scenario_from_file()
            self.run_and_check_scenario_from_file_debug()
            self.check_regtest_recon()
            self.check_active_count()
        finally:
            self.cleanup()

    def setup_network(self):
        self.log.info("Setting up network")
        self.log.info(self.warnet(f"deploy {self.network_dir}"))
        self.wait_for_all_tanks_status(target="running")
        self.wait_for_all_edges()

    def scenario_running(self, scenario_name: str):
        """Check that we are only running a single scenario of the correct name"""
        deployed = scenarios_deployed()
        assert len(deployed) == 1
        return scenario_name in deployed[0]["name"]

    def check_scenario_stopped(self):
        running = scenarios_deployed()
        self.log.debug(f"Checking if scenario stopped. Running scenarios: {len(running)}")
        return len(running) == 0

    def check_scenario_clean_exit(self):
        deployed = scenarios_deployed()
        return all(scenario["status"] == "succeeded" for scenario in deployed)

    def stop_scenario(self):
        self.log.info("Stopping running scenario")
        running = scenarios_deployed()
        assert len(running) == 1, f"Expected one running scenario, got {len(running)}"
        assert running[0]["status"] == "running", "Scenario should be running"
        stop_scenario(running[0]["name"])
        self.wait_for_predicate(self.check_scenario_stopped)

    def check_blocks(self, target_blocks, start: int = 0):
        count = int(self.warnet("bitcoin rpc tank-0000 getblockcount"))
        self.log.debug(f"Current block count: {count}, target: {start + target_blocks}")

        try:
            deployed = scenarios_deployed()
            commander = deployed[0]["commander"]
            command = f"kubectl logs {commander}"
            print("\ncommander output:")
            print(run_command(command))
            print("\n")
        except Exception:
            pass

        return count >= start + target_blocks

    def run_and_check_miner_scenario_from_file(self):
        scenario_file = self.scen_dir / "miner_std.py"
        self.log.info(f"Running scenario from file: {scenario_file}")
        self.warnet(f"run {scenario_file} --allnodes --interval=1")
        start = int(self.warnet("bitcoin rpc tank-0000 getblockcount"))
        self.wait_for_predicate(lambda: self.scenario_running("commander-minerstd"))
        self.wait_for_predicate(lambda: self.check_blocks(2, start=start))
        table = self.warnet("status")
        assert "Active Scenarios: 1" in table
        self.stop_scenario()

    def run_and_check_scenario_from_file_debug(self):
        scenario_file = self.scen_dir / "test_scenarios" / "p2p_interface.py"
        self.log.info(f"Running scenario from: {scenario_file}")
        output = self.warnet(f"run {scenario_file} --source_dir={self.scen_dir} --debug")
        self.check_for_pod_deletion_message(output)

    def run_and_check_scenario_from_file(self):
        scenario_file = self.scen_dir / "test_scenarios" / "p2p_interface.py"
        self.log.info(f"Running scenario from: {scenario_file}")
        self.warnet(f"run {scenario_file} --source_dir={self.scen_dir}")
        self.wait_for_predicate(self.check_scenario_clean_exit)

    def check_regtest_recon(self):
        scenario_file = self.scen_dir / "reconnaissance.py"
        self.log.info(f"Running scenario from file: {scenario_file}")
        self.warnet(f"run {scenario_file}")
        self.wait_for_predicate(self.check_scenario_clean_exit)

    def check_active_count(self):
        scenario_file = self.scen_dir / "test_scenarios" / "buggy_failure.py"
        self.log.info(f"Running scenario from: {scenario_file}")
        self.warnet(f"run {scenario_file} --source_dir={self.scen_dir}")

        def two_pass_one_fail():
            deployed = scenarios_deployed()
            if len([s for s in deployed if s["status"] == "succeeded"]) != 2:
                return False
            return len([s for s in deployed if s["status"] == "failed"]) == 1

        self.wait_for_predicate(two_pass_one_fail)
        table = self.warnet("status")
        assert "Active Scenarios: 0" in table

    def check_for_pod_deletion_message(self, input):
        message = "Deleting pod..."
        self.log.info(f"Checking for message: '{message}'")
        assert re.search(re.escape(message), input, flags=re.MULTILINE)
        self.log.info(f"Found message: '{message}'")


if __name__ == "__main__":
    test = ScenariosTest()
    test.run_test()
