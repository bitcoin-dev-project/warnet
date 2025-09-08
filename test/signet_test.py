#!/usr/bin/env python3

import json
import os
from pathlib import Path

from test_base import TestBase

from warnet.status import _get_deployed_scenarios as scenarios_deployed


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
            self.check_signet_recon()
            self.check_signet_scenario_miner()
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
            f"bitcoin rpc miner importdescriptors {json.dumps(self.signer_data['descriptors'])}"
        )
        self.warnet(
            f"run resources/scenarios/signet_miner.py --tank=0 generate --max-blocks=8 --min-nbits --address={self.signer_data['address']['address']}"
        )

        def block_one():
            for n in range(1, 17):
                height = int(self.warnet(f"bitcoin rpc tank-{n} getblockcount"))
                if height < 8:
                    return False
            return True

        self.wait_for_predicate(block_one)

    def check_signet_recon(self):
        scenario_file = "resources/scenarios/reconnaissance.py"
        self.log.info(f"Running scenario from file: {scenario_file}")
        self.warnet(f"run {scenario_file}")

        def check_scenario_clean_exit():
            deployed = scenarios_deployed()
            return all(scenario["status"] == "succeeded" for scenario in deployed)

        self.wait_for_predicate(check_scenario_clean_exit)

    def check_signet_scenario_miner(self):
        before_count = int(self.warnet("bitcoin rpc tank-1 getblockcount"))

        self.log.info("Generate 1 signet block from a scenario using the bitcoin-util grinder")
        self.scen_dir = Path(os.path.dirname(__file__)).parent / "resources" / "scenarios"
        scenario_file = self.scen_dir / "test_scenarios" / "signet_grinder.py"
        self.log.info(f"Running scenario from: {scenario_file}")
        self.warnet(f"run {scenario_file} --source_dir={self.scen_dir} --admin")
        self.wait_for_all_scenarios()

        after_count = int(self.warnet("bitcoin rpc tank-1 getblockcount"))
        assert after_count - before_count == 1

        deployed = scenarios_deployed()
        found = False
        for sc in deployed:
            if "grinder" in sc["name"]:
                found = True
                log = self.warnet(f"logs {sc['name']}")
                assert "Error grinding" not in log
        assert found


if __name__ == "__main__":
    test = SignetTest()
    test.run_test()
