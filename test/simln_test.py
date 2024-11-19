#!/usr/bin/env python3

import os
from pathlib import Path
from time import sleep

import pexpect
from kubernetes.stream import stream
from test_base import TestBase

from warnet.k8s import get_pods_with_label, get_static_client
from warnet.process import run_command


class LNTest(TestBase):
    def __init__(self):
        super().__init__()
        self.network_dir = Path(os.path.dirname(__file__)) / "data" / "ln"

    def run_test(self):
        try:
            os.chdir(self.tmpdir)
            self.setup_network()
            self.run_plugin()
            self.check_simln_logs()
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

        self.warnet("plugin run simln run_simln")

    def check_simln_logs(self):
        pod = get_pods_with_label("mission=plugin")
        self.log.info(run_command(f"kubectl logs pod/{pod.metadata.name}"))

    def copy_results(self) -> bool:
        self.log.info("Copying results")
        sleep(20)
        pod = get_pods_with_label("mission=plugin")[0]
        v1 = get_static_client()

        source_path = "/config/results"
        destination_path = "results"
        os.makedirs(destination_path, exist_ok=True)
        command = ["tar", "cf", "-", source_path]

        # Create the stream
        resp = stream(
            v1.connect_get_namespaced_pod_exec,
            name=pod.metadata.name,
            namespace=pod.metadata.namespace,
            command=command,
            stderr=True,
            stdin=False,
            stdout=True,
            tty=False,
            _preload_content=False,
        )

        # Write the tar output to a file
        tar_file = os.path.join(destination_path, "results.tar")
        with open(tar_file, "wb") as f:
            while resp.is_open():
                resp.update(timeout=1)
                if resp.peek_stdout():
                    f.write(resp.read_stdout().encode("utf-8"))
                if resp.peek_stderr():
                    print(resp.read_stderr())

            resp.close()

        import tarfile

        with tarfile.open(tar_file, "r") as tar:
            tar.extractall(path=destination_path)

        os.remove(tar_file)

        for root, _dirs, files in os.walk(destination_path):
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
