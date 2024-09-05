#!/usr/bin/env python3

import json
import os
import tempfile
from pathlib import Path

from test_base import TestBase

from warnet.k8s import get_default_namespace
from warnet.process import run_command


class CommanderTest(TestBase):
    def __init__(self):
        super().__init__()
        self.network_dir = Path(os.path.dirname(__file__)) / "data" / "small_2_node"

    def run_test(self):
        try:
            self.setup_network()
            self.test_generic_commander_binary()
        finally:
            self.cleanup()

    def setup_network(self):
        self.log.info("Setting up network")
        self.log.info(self.warnet(f"deploy {self.network_dir}"))
        self.wait_for_all_tanks_status(target="running")
        self.wait_for_all_edges()

    def test_generic_commander_binary(self):
        self.log.info("Launching generic commander")
        temp_file_content = """#!/usr/bin/env sh
echo 'Hello, World!'"""

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".sh") as temp_file:
            temp_file.write(temp_file_content)
            temp_file_path = temp_file.name

        os.chmod(temp_file_path, 0o755)
        self.warnet(f"run {temp_file_path}")

        # Get the commander pod name
        pods = run_command(f"kubectl get pods -n {get_default_namespace()} -o json")
        pods = json.loads(pods)
        pod_list = [item["metadata"]["name"] for item in pods["items"]]
        commander_pod = next((pod for pod in pod_list if pod.startswith("commander")), None)
        if commander_pod is None:
            raise ValueError("No pod found starting with 'commander'")
        self.log.info(f"Got pod: {commander_pod}")

        def g_log():
            logs = self.warnet(f"logs {commander_pod}")
            return "Hello, World!" in logs

        self.wait_for_predicate(g_log, timeout=60, interval=5)

        os.unlink(temp_file_path)


if __name__ == "__main__":
    test = CommanderTest()
    test.run_test()
