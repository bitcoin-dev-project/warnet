#!/usr/bin/env python3

import os
from pathlib import Path
from subprocess import PIPE, Popen

import requests
from test_base import TestBase


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
        self.log.info("Forwarding port 2323...")
        # Stays alive in background
        self.fo_port_fwd_process = Popen(
            ["kubectl", "port-forward", "fork-observer", "2323"],
            stdout=PIPE,
            stderr=PIPE,
            bufsize=1,
            universal_newlines=True,
        )

        def call_fo_api():
            try:
                fo_res = requests.get("http://localhost:2323/api/networks.json")
                network_id = fo_res.json()["networks"][0]["id"]
                fo_data = requests.get(f"http://localhost:2323/api/{network_id}/data.json")
                # fork observed!
                return len(fo_data.json()["header_infos"]) == 2
            except Exception as e:
                self.log.info(f"Fork Observer API error: {e}")
            self.log.info("No Fork observed yet")
            return False

        self.wait_for_predicate(call_fo_api)
        self.log.info("Fork observed!")
        self.fo_port_fwd_process.terminate()


if __name__ == "__main__":
    test = ServicesTest()
    test.run_test()
