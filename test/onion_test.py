#!/usr/bin/env python3

import json
import os
from pathlib import Path

from test_base import TestBase


class OnionTest(TestBase):
    def __init__(self):
        super().__init__()
        self.graph_file_path = Path(os.path.dirname(__file__)) / "data" / "12_node_ring.graphml"
        self.onion_addr = None

    def run_test(self):
        self.start_server()
        try:
            self.setup_network()
            self.test_reachability()
            self.test_onion_peer_connection()
        finally:
            self.stop_server()

    def setup_network(self):
        self.log.info("Setting up network")
        self.log.info(self.warcli(f"network start {self.graph_file_path}"))
        self.wait_for_all_tanks_status(target="running")
        self.wait_for_all_edges()

    def test_reachability(self):
        self.log.info("Checking IPv4 and onion reachability")
        self.wait_for_predicate(self.check_reachability, timeout=10 * 60)

    def check_reachability(self):
        try:
            info = json.loads(self.warcli("bitcoin rpc 0 getnetworkinfo"))
            for net in info["networks"]:
                if net["name"] == "ipv4" and not net["reachable"]:
                    return False
                if net["name"] == "onion" and not net["reachable"]:
                    return False
            if len(info["localaddresses"]) != 2:
                return False
            for addr in info["localaddresses"]:
                assert "100." in addr["address"] or ".onion" in addr["address"]
                if ".onion" in addr["address"]:
                    self.onion_addr = addr["address"]
                    return True
        except Exception as e:
            self.log.error(f"Error checking reachability: {e}")
            return False

    def test_onion_peer_connection(self):
        self.log.info("Attempting addnode to onion peer")
        self.warcli(f"bitcoin rpc 1 addnode {self.onion_addr} add")
        # Might take up to 10 minutes
        self.wait_for_predicate(self.check_onion_peer, timeout=10 * 60)

    def check_onion_peer(self):
        peers = json.loads(self.warcli("bitcoin rpc 0 getpeerinfo"))
        for peer in peers:
            self.log.debug(f"Checking peer: {peer['network']} {peer['addr']}")
            if peer["network"] == "onion":
                return True
        return False


if __name__ == "__main__":
    test = OnionTest()
    test.run_test()
