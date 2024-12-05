#!/usr/bin/env python3
import ast
import json
import os
from functools import partial
from pathlib import Path
from time import sleep
from typing import Optional

import pexpect
from ln_test import LNTest
from test_base import TestBase

from warnet.k8s import download, get_pods_with_label, pod_log, wait_for_pod
from warnet.process import run_command

lightning_selector = "mission=lightning"


class SimLNTest(LNTest, TestBase):
    def __init__(self):
        super().__init__()
        self.network_dir = Path(os.path.dirname(__file__)) / "data" / "ln"
        self.plugins_dir = Path(os.path.dirname(__file__)).parent / "resources" / "plugins"

    def run_test(self):
        try:
            os.chdir(self.tmpdir)
            self.init_directory()

            self.import_network()
            self.setup_network()
            self.run_ln_init_scenario()
            self.run_simln()

            self.copy_results()
            self.run_activity()
            self.run_activity_with_user_dir()
        finally:
            self.cleanup()

    def init_directory(self):
        self.log.info("Initializing SimLN plugin...")
        self.sut = pexpect.spawn("warnet init")
        self.sut.expect("network", timeout=10)
        self.sut.sendline("n")
        self.sut.close()

    def copy_results(self):
        self.log.info("Copying results")
        pod = get_pods_with_label("mission=simln")[0]
        self.wait_for_gossip_sync(2)
        wait_for_pod(pod.metadata.name, 60)

        log_resp = pod_log(pod.metadata.name, "simln")
        self.log.info(log_resp.data.decode("utf-8"))

        partial_func = partial(self.found_results_remotely, pod.metadata.name)
        self.wait_for_predicate(partial_func)

        download(pod.metadata.name, Path("/working/results"), Path("."), pod.metadata.namespace)
        self.wait_for_predicate(self.found_results_locally)

    def run_activity(self):
        cmd = "warnet plugins simln get-example-activity"
        self.log.info(f"Activity: {cmd}")
        activity_result = run_command(cmd)
        activity = json.loads(activity_result)
        pod_result = run_command(f"warnet plugins simln launch-activity '{json.dumps(activity)}'")
        self.log.info(f"launched activity: {pod_result}")
        partial_func = partial(self.found_results_remotely, pod_result.strip())
        self.wait_for_predicate(partial_func)
        self.log.info("Successfully ran activity")

    def run_activity_with_user_dir(self):
        cmd = "mkdir temp; cd temp; warnet --user-dir ../ plugins simln get-example-activity; cd ../; rm -rf temp"
        self.log.info(f"Activity: {cmd}")
        activity_result = run_command(cmd)
        activity = json.loads(activity_result)
        pod_result = run_command(f"warnet plugins simln launch-activity '{json.dumps(activity)}'")
        self.log.info(f"launched activity: {pod_result}")
        partial_func = partial(self.found_results_remotely, pod_result.strip())
        self.wait_for_predicate(partial_func)
        run_command("cd ../")
        self.log.info("Successfully ran activity using --user-dir")

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

    def found_results_remotely(self, pod: Optional[str] = None) -> bool:
        if pod is None:
            pod_names_literal = run_command("warnet plugins simln list-simln-podnames")
            pod_names = ast.literal_eval(pod_names_literal)
            pod = pod_names[0]
        self.log.info(f"Checking for results file in {pod}")
        results_file = run_command(f"warnet plugins simln sh {pod} ls /working/results").strip()
        self.log.info(f"Results file: {results_file}")
        results = run_command(
            f"warnet plugins simln sh {pod} cat /working/results/{results_file}"
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
