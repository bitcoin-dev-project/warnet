#!/usr/bin/env python3
import ast
import json
import os
from functools import partial
from pathlib import Path
from time import sleep
from typing import Optional

import pexpect
from test_base import TestBase

from warnet.constants import LIGHTNING_MISSION
from warnet.k8s import download, get_mission, wait_for_pod
from warnet.process import run_command


class SimLNTest(TestBase):
    def __init__(self):
        super().__init__()
        self.network_dir = Path(os.path.dirname(__file__)) / "data" / "ln"
        self.plugins_dir = Path(os.path.dirname(__file__)).parent / "resources" / "plugins"
        self.simln_exec = "plugins/simln/simln.py"

    def run_test(self):
        try:
            os.chdir(self.tmpdir)
            self.init_directory()
            self.deploy_with_plugin()
            self.copy_results()
        finally:
            self.cleanup()

    def init_directory(self):
        self.log.info("Initializing SimLN plugin...")
        self.sut = pexpect.spawn("warnet init")
        self.sut.expect("network", timeout=10)
        self.sut.sendline("n")
        self.sut.close()

    def deploy_with_plugin(self):
        self.log.info("Deploy the ln network with a SimLN plugin")
        results = self.warnet(f"deploy {self.network_dir}")
        self.log.info(results)
        wait_for_pod(self.get_first_simln_pod())

    def copy_results(self):
        pod = self.get_first_simln_pod()
        partial_func = partial(self.found_results_remotely, pod)
        self.wait_for_predicate(partial_func)

        download(pod, Path("/working/results"), Path("."))
        self.wait_for_predicate(self.found_results_locally)

    def wait_for_gossip_sync(self, expected: int):
        self.log.info(f"Waiting for sync (expecting {expected})...")
        current = 0
        while current < expected:
            current = 0
            pods = get_mission(LIGHTNING_MISSION)
            for v1_pod in pods:
                node = v1_pod.metadata.name
                chs = json.loads(run_command(f"warnet ln rpc {node} describegraph"))["edges"]
                self.log.info(f"{node}: {len(chs)} channels")
                current += len(chs)
            sleep(1)
        self.log.info("Synced")

    def found_results_remotely(self, pod: Optional[str] = None) -> bool:
        if pod is None:
            pod = self.get_first_simln_pod()
        self.log.info(f"Checking for results file in {pod}")
        results_file = run_command(f"{self.simln_exec} sh {pod} ls /working/results").strip()
        self.log.info(f"Results file: {results_file}")
        results = run_command(
            f"{self.simln_exec} sh {pod} cat /working/results/{results_file}"
        ).strip()
        self.log.info(results)
        return results.find("Success") > 0

    def get_first_simln_pod(self):
        command = f"{self.simln_exec} list-pod-names"
        pod_names_literal = run_command(command)
        self.log.info(f"{command}: {pod_names_literal}")
        pod_names = ast.literal_eval(pod_names_literal)
        return pod_names[0]

    def found_results_locally(self) -> bool:
        directory = "results"
        self.log.info(f"Searching {directory}")
        for root, _dirs, files in os.walk(Path(directory)):
            for file_name in files:
                file_path = os.path.join(root, file_name)

                with open(file_path) as file:
                    content = file.read()
                    if "Success" in content:
                        self.log.info(f"Found downloaded results in directory: {directory}.")
                        return True
        self.log.info(f"Did not find downloaded results in directory: {directory}.")
        return False


if __name__ == "__main__":
    test = SimLNTest()
    test.run_test()
