#!/usr/bin/env python3

import json
import os
from pathlib import Path

from test_base import TestBase


class BuildBranchTest(TestBase):
    def __init__(self):
        super().__init__()
        self.graph_file_path = Path(os.path.dirname(__file__)) / "data" / "build_v24_test.graphml"

    def run_test(self):
        self.start_server()
        try:
            self.setup_network()
            self.wait_for_p2p_connections()
            self.check_build_flags()
        finally:
            self.stop_server()

    def setup_network(self):
        self.log.info("Setting up network")
        self.log.info(self.warcli(f"network start {self.graph_file_path}"))
        self.wait_for_all_tanks_status(target="running", timeout=10 * 60)
        self.wait_for_all_edges()

    def wait_for_p2p_connections(self):
        self.log.info("Waiting for P2P connections")
        self.wait_for_predicate(self.check_peers, timeout=5 * 60)

    def check_peers(self):
        info0 = json.loads(self.warcli("bitcoin rpc 0 getpeerinfo"))
        info1 = json.loads(self.warcli("bitcoin rpc 1 getpeerinfo"))
        self.log.debug(
            f"Waiting for both nodes to get one peer: node0: {len(info0)}, node1: {len(info1)}"
        )
        return len(info0) == 1 and len(info1) == 1

    def check_build_flags(self):
        self.log.info("Checking build flags")
        release_help = self.get_tank(0).exec("bitcoind -h")
        build_help = self.get_tank(1).exec("bitcoind -h")

        assert "zmqpubhashblock" in release_help, "zmqpubhashblock not found in release help"
        assert (
            "zmqpubhashblock" not in build_help
        ), "zmqpubhashblock found in build help, but it shouldn't be"

        self.log.info("Build flags check passed")


if __name__ == "__main__":
    test = BuildBranchTest()
    test.run_test()
