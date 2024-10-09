#!/usr/bin/env python3

import json
import os
from pathlib import Path
from time import sleep

import requests
from test_base import TestBase

from warnet.k8s import get_ingress_ip_or_host, wait_for_ingress_controller


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

        self.log.info("Waiting for ingress controller")
        wait_for_ingress_controller()

        self.log.info("Waiting for ingress host")
        ingress_ip = None
        attempts = 100
        while not ingress_ip:
            ingress_ip = get_ingress_ip_or_host()
            attempts -= 1
            if attempts < 0:
                raise Exception("Never got ingress host")
            sleep(1)
        # network id is 0xDEADBE in decimal
        fo_data_uri = f"http://{ingress_ip}/fork-observer/api/14593470/data.json"

        def call_fo_api():
            # if on minikube remember to run `minikube tunnel` for this test to run
            try:
                self.log.info(f"Getting: {fo_data_uri}")
                fo_data = requests.get(fo_data_uri)
                # fork observed!
                return len(fo_data.json()["header_infos"]) == 2
            except Exception as e:
                self.log.info(f"Fork Observer API error: {e}")
            self.log.info("No Fork observed yet")
            return False

        self.wait_for_predicate(call_fo_api)
        self.log.info("Fork observed!")

        self.log.info("Checking node description...")
        fo_data = requests.get(fo_data_uri)
        nodes = fo_data.json()["nodes"]
        assert len(nodes) == 4
        assert nodes[1]["name"] == "john"
        assert nodes[1]["description"] == "john.default.svc:18444"

        self.log.info("Checking reachable address is provided...")
        self.warnet("bitcoin rpc george addnode john.default.svc:18444 onetry")
        self.wait_for_predicate(
            lambda: len(json.loads(self.warnet("bitcoin rpc george getpeerinfo"))) > 1
        )


if __name__ == "__main__":
    test = ServicesTest()
    test.run_test()
