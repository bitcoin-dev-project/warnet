#!/usr/bin/env python3

import json
import os
import tempfile
import time
from pathlib import Path

from test_base import TestBase

from warnet.k8s import get_default_namespace
from warnet.process import run_command


class BinaryTest(TestBase):
    TEST_STRING = "Hello, World!"

    def __init__(self):
        super().__init__()
        self.network_dir = Path(os.path.dirname(__file__)) / "data" / "small_2_node"

    def run_test(self):
        try:
            self.setup_network()
            self.test_generic_binary()
        finally:
            self.cleanup()

    def setup_network(self):
        self.log.info("Setting up network")
        self.log.info(self.warnet(f"deploy {self.network_dir}"))
        self.wait_for_all_tanks_status(target="running")
        self.wait_for_all_edges()

    def test_generic_binary(self):
        self.log.info("Launching binary")
        temp_file_content = f"""#!/usr/bin/env sh
echo {self.TEST_STRING}"""

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".sh") as temp_file:
            temp_file.write(temp_file_content)
            temp_file_path = temp_file.name

        os.chmod(temp_file_path, 0o755)
        self.warnet(f"run-binary {temp_file_path}")

        # Get the commander pod name
        pods = run_command(f"kubectl get pods -n {get_default_namespace()} -o json")
        pods = json.loads(pods)
        pod_list = [item["metadata"]["name"] for item in pods["items"]]
        binary_pod = next((pod for pod in pod_list if pod.startswith("binary")), None)
        if binary_pod is None:
            raise ValueError("No pod found starting with 'binary'")
        self.log.info(f"Got pod: {binary_pod}")

        def g_log():
            logs = self.warnet(f"logs {binary_pod}")
            return self.TEST_STRING in logs

        time.sleep(5)
        self.wait_for_predicate(g_log, timeout=60, interval=5)

        os.unlink(temp_file_path)


if __name__ == "__main__":
    test = BinaryTest()
    test.run_test()
