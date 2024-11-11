#!/usr/bin/env python3

import os
from pathlib import Path

import pexpect
from test_base import TestBase


class HooksTest(TestBase):
    def __init__(self):
        super().__init__()
        self.network_dir = Path(os.path.dirname(__file__)) / "data" / "12_node_ring"

    def run_test(self):
        try:
            os.chdir(self.tmpdir)
            self.setup_network()
            self.generate_plugin_dir()

        finally:
            self.cleanup()

    def setup_network(self):
        self.log.info("Setting up network")
        self.log.info(self.warnet(f"deploy {self.network_dir}"))
        self.wait_for_all_tanks_status(target="running")
        self.wait_for_all_edges()

    def generate_plugin_dir(self):
        self.log.info("Generating the plugin directroy")
        self.sut = pexpect.spawn("warnet init")
        self.sut.expect("Do you want to create a custom network?", timeout=10)
        self.sut.sendline("n")
        plugin_dir = Path(os.getcwd()) / "plugins"
        assert plugin_dir.exists()


if __name__ == "__main__":
    test = HooksTest()
    test.run_test()
