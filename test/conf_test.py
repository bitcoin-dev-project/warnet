#!/usr/bin/env python3

import json
import os
import re
from pathlib import Path

from test_base import TestBase

from warnet.control import stop_scenario
from warnet.k8s import get_mission
from warnet.status import _get_deployed_scenarios as scenarios_deployed


class ConfTest(TestBase):
    def __init__(self):
        super().__init__()
        self.network_dir = Path(os.path.dirname(__file__)) / "data" / "bitcoin_conf"
        self.scen_dir = Path(os.path.dirname(__file__)).parent / "resources" / "scenarios"

    def run_test(self):
        try:
            self.setup_network()
            self.check_uacomment()
            self.check_single_miner()
        finally:
            self.cleanup()

    def setup_network(self):
        self.log.info("Setting up network")
        self.log.info(self.warnet(f"deploy {self.network_dir}"))
        self.wait_for_all_tanks_status(target="running")

    def check_uacomment(self):
        tanks = get_mission("tank")

        def get_uacomment():
            for tank in tanks[::-1]:
                try:
                    name = tank.metadata.name
                    info = json.loads(self.warnet(f"bitcoin rpc {name} getnetworkinfo"))
                    subver = info["subversion"]

                    # Regex pattern to match the uacomment inside parentheses
                    # e.g. /Satoshi:27.0.0(tank-0027)/
                    pattern = r"\(([^)]+)\)"
                    match = re.search(pattern, subver)
                    if match:
                        uacomment = match.group(1)
                        assert uacomment == name
                    else:
                        return False
                except Exception:
                    return False
            return True

        self.wait_for_predicate(get_uacomment)

    def check_single_miner(self):
        scenario_file = self.scen_dir / "miner_std.py"
        self.log.info(f"Running scenario from: {scenario_file}")
        # Mine from a tank that is not first or last and
        # is one of the only few in the network that even
        # has rpc reatewallet method!
        self.warnet(f"run {scenario_file} --tank=tank-0026 --interval=1")
        self.wait_for_predicate(
            lambda: int(self.warnet("bitcoin rpc tank-0026 getblockcount")) >= 10
        )
        running = scenarios_deployed()
        assert len(running) == 1, f"Expected one running scenario, got {len(running)}"
        assert running[0]["status"] == "running", "Scenario should be running"
        stop_scenario(running[0]["name"])
        self.wait_for_all_scenarios()


if __name__ == "__main__":
    test = ConfTest()
    test.run_test()
