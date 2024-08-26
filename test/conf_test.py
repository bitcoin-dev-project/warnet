#!/usr/bin/env python3

import json
import os
import re
from pathlib import Path

from test_base import TestBase

from warnet.k8s import get_mission


class ConfTest(TestBase):
    def __init__(self):
        super().__init__()
        self.network_dir = Path(os.path.dirname(__file__)) / "data" / "bitcoin_conf"

    def run_test(self):
        try:
            self.setup_network()
            self.check_uacomment()
        finally:
            self.stop_server()

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


if __name__ == "__main__":
    test = ConfTest()
    test.run_test()
