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
        self.sut = pexpect.spawn("warnet create-network")
        self.sut.expect("init", timeout=5)

    def directory_exists(self):
        self.sut = pexpect.spawn("warnet create-network")
        self.sut.expect("name", timeout=1)
        self.sut.sendline("ANewNetwork")
        self.sut.expect("many", timeout=1)
        self.sut.sendline("")
        self.sut.expect("connections", timeout=1)
        self.sut.sendline("")
        self.sut.expect("version", timeout=1)
        self.sut.sendline("")
        self.sut.expect("successfully", timeout=5)


if __name__ == "__main__":
    test = GraphTest()
    test.run_test()
