#!/usr/bin/env python3

import os
from pathlib import Path

import requests
from test_base import TestBase

from warnet.k8s import get_ingress_ip_or_host


class ServicesTest(TestBase):
    def __init__(self):
        super().__init__()
        self.network_dir = Path(os.path.dirname(__file__)) / "data" / "services"

    def run_test(self):
        try:
            self.setup_network()
            self.check_fork_observer()
        finally:
            self.cleanup()

    def setup_network(self):
        self.log.info("Setting up network")
        self.log.info(self.warnet(f"deploy {self.network_dir}"))
        self.wait_for_all_tanks_status(target="running")
        self.wait_for_all_edges()

    def check_fork_observer(self):
        self.log.info("Creating chain split")
        self.warnet("bitcoin rpc john createwallet miner")
        self.warnet("bitcoin rpc john -generate 1")
        # Port will be auto-forwarded by `warnet deploy`, routed through the enabled Caddy pod

        def call_fo_api():
            # if on minikube remember to run `minikube tunnel` for this test to run
            ingress_ip = get_ingress_ip_or_host()
            fo_root = f"http://{ingress_ip}/fork-observer"
            try:
                fo_res = requests.get(f"{fo_root}/api/networks.json")
                network_id = fo_res.json()["networks"][0]["id"]
                fo_data = requests.get(f"{fo_root}/api/{network_id}/data.json")
                # fork observed!
                return len(fo_data.json()["header_infos"]) == 2
            except Exception as e:
                self.log.info(f"Fork Observer API error: {e}")
            self.log.info("No Fork observed yet")
            return False

        self.wait_for_predicate(call_fo_api)
        self.log.info("Fork observed!")


if __name__ == "__main__":
    test = ServicesTest()
    test.run_test()
