#!/usr/bin/env python3
import ast
import os
from functools import partial
from pathlib import Path
from typing import Optional

from test_base import TestBase

from warnet.k8s import download, wait_for_pod
from warnet.process import run_command


class PluginTest(TestBase):
    def __init__(self):
        super().__init__()
        self.network_dir = Path(os.path.dirname(__file__)) / "data" / "network_with_plugins"
        self.plugins_dir = Path(os.path.dirname(__file__)).parent / "resources" / "plugins"
        self.simln_exec = self.plugins_dir / "simln" / "plugin.py"

    def run_test(self):
        try:
            os.chdir(self.tmpdir)
            self.deploy_with_plugin()
            self.copy_results()
            self.assert_hello_plugin()
        finally:
            self.cleanup()

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

    def assert_hello_plugin(self):
        self.log.info("Waiting for the 'hello' plugin pods.")
        wait_for_pod("hello-pre-deploy")
        wait_for_pod("hello-post-deploy")
        wait_for_pod("hello-pre-network")
        wait_for_pod("hello-post-network")
        wait_for_pod("tank-0000-post-hello-pod")
        wait_for_pod("tank-0000-pre-hello-pod")
        wait_for_pod("tank-0001-post-hello-pod")
        wait_for_pod("tank-0001-pre-hello-pod")
        wait_for_pod("tank-0002-post-hello-pod")
        wait_for_pod("tank-0002-pre-hello-pod")
        wait_for_pod("tank-0003-post-hello-pod")
        wait_for_pod("tank-0003-pre-hello-pod")
        wait_for_pod("tank-0004-post-hello-pod")
        wait_for_pod("tank-0004-pre-hello-pod")
        wait_for_pod("tank-0005-post-hello-pod")
        wait_for_pod("tank-0005-pre-hello-pod")


if __name__ == "__main__":
    test = PluginTest()
    test.run_test()
