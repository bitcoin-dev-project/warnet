#!/usr/bin/env python3

import os
from pathlib import Path

import pexpect
from test_base import TestBase

from warnet.k8s import get_kubeconfig_value
from warnet.process import stream_command


class WargamesTest(TestBase):
    def __init__(self):
        super().__init__()
        self.wargame_dir = Path(os.path.dirname(__file__)) / "data" / "wargames"
        self.scen_src_dir = Path(os.path.dirname(__file__)).parent / "resources" / "scenarios"
        self.scen_test_dir = (
            Path(os.path.dirname(__file__)).parent / "resources" / "scenarios" / "test_scenarios"
        )
        self.initial_context = get_kubeconfig_value("{.current-context}")

    def run_test(self):
        try:
            self.setup_battlefield()
            self.setup_armies()
            self.check_scenario_permissions()
        finally:
            self.log.info("Restoring initial_context")
            stream_command(f"kubectl config use-context {self.initial_context}")
            self.cleanup()

    def setup_battlefield(self):
        self.log.info("Setting up battlefield")
        self.log.info(self.warnet(f"deploy {self.wargame_dir / 'networks' / 'battlefield'}"))
        self.wait_for_all_tanks_status(target="running")
        self.wait_for_all_edges()

    def setup_armies(self):
        self.log.info("Deploying namespaces and armadas")
        self.log.info(self.warnet(f"deploy {self.wargame_dir / 'namespaces' / 'armies'}"))
        self.log.info(
            self.warnet(f"deploy {self.wargame_dir / 'networks' / 'armada'} --to-all-users")
        )
        self.wait_for_all_tanks_status(target="running")
        self.wait_for_all_edges()

    def check_scenario_permissions(self):
        self.log.info("Admin without --admin can not command a node outside of default namespace")
        stream_command(
            f"warnet run {self.scen_test_dir / 'generate_one_allnodes.py'} --source_dir={self.scen_src_dir} --debug"
        )
        # Only miner.default and target-red.default were accesible
        assert self.warnet("bitcoin rpc miner getblockcount") == "2"

        self.log.info("Admin with --admin can command all nodes in any namespace")
        stream_command(
            f"warnet run {self.scen_test_dir / 'generate_one_allnodes.py'} --source_dir={self.scen_src_dir} --admin --debug"
        )
        # armada.wargames-red, miner.default and target-red.default were accesible
        assert self.warnet("bitcoin rpc miner getblockcount") == "5"

        self.log.info("Switch to wargames player context")
        self.log.info(self.warnet("admin create-kubeconfigs"))
        clicker = pexpect.spawn("warnet auth kubeconfigs/warnet-user-wargames-red-kubeconfig")
        while clicker.expect(["Overwrite", "Updated kubeconfig"]) == 0:
            print(clicker.before, clicker.after)
            clicker.sendline("y")
        print(clicker.before, clicker.after)

        self.log.info("Player without --admin can only command the node inside their own namespace")
        stream_command(
            f"warnet run {self.scen_test_dir / 'generate_one_allnodes.py'} --source_dir={self.scen_src_dir} --debug"
        )
        # Only armada.wargames-red was (and is) accesible
        assert self.warnet("bitcoin rpc armada getblockcount") == "6"

        self.log.info("Player attempting to use --admin is gonna have a bad time")
        stream_command(
            f"warnet run {self.scen_test_dir / 'generate_one_allnodes.py'} --source_dir={self.scen_src_dir} --admin --debug"
        )
        # Nothing was accesible
        assert self.warnet("bitcoin rpc armada getblockcount") == "6"

        self.log.info("Restore admin context")
        stream_command(f"kubectl config use-context {self.initial_context}")
        # Sanity check
        assert self.warnet("bitcoin rpc miner getblockcount") == "6"


if __name__ == "__main__":
    test = WargamesTest()
    test.run_test()
