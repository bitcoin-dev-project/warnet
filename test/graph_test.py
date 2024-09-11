#!/usr/bin/env python3

import os
import shutil

import pexpect
from test_base import TestBase

NETWORKS_DIR = "networks"


class GraphTest(TestBase):
    def __init__(self):
        super().__init__()

    def run_test(self):
        try:
            self.directory_not_exist()
            os.mkdir(NETWORKS_DIR)
            self.directory_exists()

        finally:
            shutil.rmtree(NETWORKS_DIR) if os.path.exists(NETWORKS_DIR) else None

    def directory_not_exist(self):
        self.sut = pexpect.spawn("warnet create")
        self.sut.expect("init", timeout=50)

    def directory_exists(self):
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


if __name__ == "__main__":
    test = GraphTest()
    test.run_test()
