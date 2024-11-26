#!/usr/bin/env python3
import ast
import json
import os
from pathlib import Path
from time import sleep

import pexpect
from test_base import TestBase

from warnet.k8s import download, get_pods_with_label, pod_log, wait_for_pod
from warnet.process import run_command

lightning_selector = "mission=lightning"

UP = "\033[A"
DOWN = "\033[B"
ENTER = "\n"


class SimLNTest(TestBase):
    def __init__(self):
        super().__init__()
        self.network_dir = Path(os.path.dirname(__file__)) / "data" / "ln"

    def run_test(self):
        try:
            os.chdir(self.tmpdir)
            self.setup_network()
            self.run_plugin()
            self.copy_results()
        finally:
            self.cleanup()

    def setup_network(self):
        self.log.info("Setting up network")
        self.log.info(self.warnet(f"deploy {self.network_dir}"))
        self.wait_for_all_tanks_status(target="running")

    def run_plugin(self):
        self.log.info("Initializing SimLN plugin...")
        self.sut = pexpect.spawn("warnet init")
        self.sut.expect("network", timeout=10)
        self.sut.sendline("n")
        self.sut.close()

        cmd = "warnet plugins simln run-demo"
        self.log.info(f"Running: {cmd}")
        run_command(cmd)
        self.wait_for_predicate(self.found_results_remotely)
        self.log.info("Ran SimLn plugin.")

    def copy_results(self) -> bool:
        self.log.info("Copying results")
        pod = get_pods_with_label("mission=simln")[0]
        self.wait_for_gossip_sync(2)
        wait_for_pod(pod.metadata.name, 60)

        log_resp = pod_log(pod.metadata.name, "simln")
        self.log.info(log_resp.data.decode("utf-8"))

        download(pod.metadata.name, Path("/working/results"), Path("."), pod.metadata.namespace)
        self.wait_for_predicate(self.found_results_locally)

    def wait_for_gossip_sync(self, expected: int):
        self.log.info(f"Waiting for sync (expecting {expected})...")
        current = 0
        while current < expected:
            current = 0
            pods = get_pods_with_label(lightning_selector)
            for v1_pod in pods:
                node = v1_pod.metadata.name
                chs = json.loads(run_command(f"warnet ln rpc {node} describegraph"))["edges"]
                self.log.info(f"{node}: {len(chs)} channels")
                current += len(chs)
            sleep(1)
        self.log.info("Synced")

    def found_results_remotely(self) -> bool:
        pod_names_literal = run_command("warnet plugins simln list-simln-podnames")
        pod_names = ast.literal_eval(pod_names_literal)
        pod = pod_names[0]
        self.log.info(f"Checking for results file in {pod}")
        results_file = run_command(f"warnet plugins simln rpc {pod} ls /working/results").strip()
        self.log.info(f"Results file: {results_file}")
        results = run_command(
            f"warnet plugins simln rpc {pod} cat /working/results/{results_file}"
        ).strip()
        self.log.info(results)
        return results.find("Success") > 0

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
