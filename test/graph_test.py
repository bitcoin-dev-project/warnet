#!/usr/bin/env python3

import json
import os

import pexpect
from test_base import TestBase

NETWORKS_DIR = "networks"


class GraphTest(TestBase):
    def __init__(self):
        super().__init__()

    def run_test(self):
        try:
            # cwd out of the git repo for remainder of script
            os.chdir(self.tmpdir)
            self.directory_not_exist()
            os.mkdir(NETWORKS_DIR)
            self.directory_exists()
            self.run_created_network()
        finally:
            self.cleanup()

    def directory_not_exist(self):
        try:
            self.log.info("testing warnet create, dir doesn't exist")
            self.sut = pexpect.spawn("warnet create")
            self.sut.expect("init", timeout=10)
        except Exception as e:
            print(f"\nReceived prompt text:\n  {self.sut.before.decode('utf-8')}\n")
            raise e

    def directory_exists(self):
        try:
            self.log.info("testing warnet create, dir does exist")
            self.sut = pexpect.spawn("warnet create")
            self.sut.expect("name", timeout=10)
            self.sut.sendline("ANewNetwork")
            self.sut.expect("many", timeout=10)
            self.sut.sendline("")
            self.sut.expect("connections", timeout=10)
            self.sut.sendline("")
            self.sut.expect("version", timeout=10)
            self.sut.sendline("")
            self.sut.expect("enable fork-observer", timeout=10)
            self.sut.sendline("")
            self.sut.expect("seconds", timeout=10)
            self.sut.sendline("")
            self.sut.expect("enable grafana", timeout=10)
            self.sut.sendline("")
            self.sut.expect("successfully", timeout=50)
        except Exception as e:
            print(f"\nReceived prompt text:\n  {self.sut.before.decode('utf-8')}\n")
            raise e

    def run_created_network(self):
        self.log.info("adding custom config to one tank")
        with open("networks/ANewNetwork/network.yaml") as f:
            s = f.read()
        s = s.replace("  name: tank-0000\n", "  name: tank-0000\n  config: debug=mempool\n")
        with open("networks/ANewNetwork/network.yaml", "w") as f:
            f.write(s)

        self.log.info("deploying new network")
        self.warnet("deploy networks/ANewNetwork")
        self.wait_for_all_tanks_status(target="running")
        debugs = json.loads(self.warnet("bitcoin rpc tank-0000 logging"))
        # set in defaultConfig
        assert debugs["rpc"]
        # set in config just for this tank
        assert debugs["mempool"]
        # santy check
        assert not debugs["zmq"]


if __name__ == "__main__":
    test = GraphTest()
    test.run_test()
