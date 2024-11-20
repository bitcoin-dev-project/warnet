#!/usr/bin/env python3

import os
from pathlib import Path
from subprocess import run
from time import sleep

import pexpect
from test_base import TestBase

from warnet.k8s import download, get_pods_with_label


class LNTest(TestBase):
    def __init__(self):
        super().__init__()
        self.network_dir = Path(os.path.dirname(__file__)) / "data" / "ln"

    def run_test(self):
        try:
            os.chdir(self.tmpdir)
            self.setup_network()
            self.run_plugin()
            result = self.copy_results()
            assert result
        finally:
            self.cleanup()

    def setup_network(self):
        self.log.info("Setting up network")
        self.log.info(self.warnet(f"deploy {self.network_dir}"))
        self.wait_for_all_tanks_status(target="running")

    def run_plugin(self):
        self.sut = pexpect.spawn("warnet init")
        self.sut.expect("network", timeout=10)
        self.sut.sendline("n")
        self.sut.close()

        self.log.info(run(["warnet", "plugin", "run", "simln", "run_simln"]))
        sleep(10)

    def copy_results(self) -> bool:
        self.log.info("Copying results")
        sleep(20)
        pod = get_pods_with_label("mission=plugin")[0]

        download(pod.metadata.name, pod.metadata.namespace, Path("/working/results"), Path("."))

        for root, _dirs, files in os.walk(Path("results")):
            for file_name in files:
                file_path = os.path.join(root, file_name)

                with open(file_path) as file:
                    content = file.read()
                    if "Success" in content:
                        return True
        return False


if __name__ == "__main__":
    test = LNTest()
    test.run_test()
