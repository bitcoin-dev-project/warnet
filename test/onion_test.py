#!/usr/bin/env python3

import json
import os
from pathlib import Path

from test_base import TestBase

from warnet.k8s import pod_log


class OnionTest(TestBase):
    def __init__(self):
        super().__init__()
        self.network_dir = Path(os.path.dirname(__file__)) / "data" / "onion"

    def run_test(self):
        try:
            self.setup_network()
            self.check_tor()
        finally:
            self.cleanup()

    def setup_network(self):
        self.log.info("Setting up network")
        self.log.info(self.warnet(f"deploy {self.network_dir}"))
        self.wait_for_all_tanks_status(target="running")

    def check_tor(self):
        onions = {"tank-0001": None, "tank-0002": None}

        def get_onions():
            peers = ["tank-0001", "tank-0002"]
            for tank in peers:
                if not onions[tank]:
                    self.log.info(f"Getting local onion address from {tank}...")
                    info = json.loads(self.warnet(f"bitcoin rpc {tank} getnetworkinfo"))
                    for addr in info["localaddresses"]:
                        if "onion" in addr["address"]:
                            onions[tank] = addr["address"]
                            self.log.info(f" ... got: {addr['address']}")
            return all(onions[tank] for tank in peers)

        self.wait_for_predicate(get_onions)

        self.log.info("Adding 1 block")
        self.warnet("bitcoin rpc tank-0001 createwallet miner")
        self.warnet("bitcoin rpc tank-0001 -generate 1")

        self.log.info("Adding connections via onion: 0000->0001->0002")
        self.warnet(f"bitcoin rpc tank-0000 addnode {onions['tank-0001']} add")
        self.warnet(f"bitcoin rpc tank-0001 addnode {onions['tank-0002']} add")

        def onion_connect():
            peers = json.loads(self.warnet("bitcoin rpc tank-0001 getpeerinfo"))
            self.log.info("\n")
            self.log.info("Waiting for tank-0001 to have at least two onion peers:")
            self.log.info(json.dumps(peers, indent=2))
            if len(peers) >= 2:
                for peer in peers:
                    assert peer["network"] == "onion"
                return True
            else:
                self.log.info("tank-0001 tor log tail:")
                stream = pod_log(
                    pod_name="tank-0001",
                    container_name="tor",
                    namespace="default",
                    follow=False,
                    tail_lines=5,
                )
                for line in stream:
                    msg = line.decode("utf-8").rstrip()
                    msg = msg.split("]")
                    self.log.info(msg[-1])

        self.wait_for_predicate(onion_connect, timeout=20 * 60)


if __name__ == "__main__":
    test = OnionTest()
    test.run_test()
