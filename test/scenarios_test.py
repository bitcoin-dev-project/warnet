#!/usr/bin/env python3

import os
from pathlib import Path

from test_base import TestBase

from warnet.cli.k8s import delete_pod
from warnet.cli.scenarios import _active as scenarios_active
from warnet.cli.scenarios import _available as scenarios_available
from warnet.cli.process import run_command

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
        self.log.info(self.warcli(f"network deploy {self.network_dir}"))
        self.wait_for_all_tanks_status(target="running")
        self.wait_for_all_edges()

    def test_scenarios(self):
        self.check_available_scenarios()
        self.run_and_check_miner_scenario()
        self.run_and_check_miner_scenario_from_file()
        self.run_and_check_scenario_from_file()

    def check_available_scenarios(self):
        self.log.info("Checking available scenarios")
        # Use rpc instead of warcli so we get raw JSON object
        scenarios = scenarios_available()
        assert len(scenarios) == 4, f"Expected 4 available scenarios, got {len(scenarios)}"
        self.log.info(f"Found {len(scenarios)} available scenarios")

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
        self.warcli(f"scenarios run-file {scenario_file}")
        self.wait_for_predicate(lambda: check_scenario_clean_exit())

    def run_and_check_miner_scenario(self):
        sc = "miner_std"
        self.log.info(f"Running scenario {sc}")
        self.warcli(f"scenarios run {sc} --allnodes --interval=1")
        self.wait_for_predicate(lambda: self.scenario_running("commander-minerstd"))
        self.wait_for_predicate(lambda: self.check_blocks(30))
        self.stop_scenario()

    def run_and_check_miner_scenario_from_file(self):
        scenario_file = "src/warnet/scenarios/miner_std.py"
        self.log.info(f"Running scenario from file: {scenario_file}")
        self.warcli(f"scenarios run-file {scenario_file} --allnodes --interval=1")
        start = int(self.warcli("bitcoin rpc tank-0000 getblockcount"))
        self.wait_for_predicate(lambda: self.scenario_running("commander-minerstd"))
        self.wait_for_predicate(lambda: self.check_blocks(2, start=start))
        self.stop_scenario()

    def check_blocks(self, target_blocks, start: int = 0):
        count = int(self.warcli("bitcoin rpc tank-0000 getblockcount"))
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
