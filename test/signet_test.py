#!/usr/bin/env python3

import json
import os
from pathlib import Path

from test_base import TestBase


class SignetTest(TestBase):
    def __init__(self):
        super().__init__()
        self.network_dir = Path(os.path.dirname(__file__)) / "data" / "signet"
        signer_data_path = Path(os.path.dirname(__file__)) / "data" / "signet-signer.json"
        with open(signer_data_path) as f:
            self.signer_data = json.loads(f.read())

    def run_test(self):
        try:
            self.setup_network()
            self.check_signet_miner()
        finally:
            self.cleanup()

    def setup_network(self):
        self.log.info("Setting up network")
        self.log.info(self.warnet(f"deploy {self.network_dir}"))
        self.wait_for_all_tanks_status(target="running")
        self.wait_for_all_edges()

    def check_signet_miner(self):
        self.warnet("bitcoin rpc miner createwallet miner")
        self.warnet(
            f"bitcoin rpc miner importdescriptors '{json.dumps(self.signer_data['descriptors'])}'"
        )
        self.warnet(
            f"run resources/scenarios/signet_miner.py --tank=0 generate --min-nbits --address={self.signer_data['address']['address']}"
        )

        def block_one():
            for n in range(1, 11):
                height = int(self.warnet(f"bitcoin rpc tank-{n} getblockcount"))
                if height != 1:
                    return False
            return True

        self.wait_for_predicate(block_one)


if __name__ == "__main__":
    test = SignetTest()
    test.run_test()
