#!/usr/bin/env python3
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

        cmd = "warnet plugin run"
        self.log.info(cmd)
        self.sut = pexpect.spawn(cmd)
        self.sut.expect("simln", timeout=10)
        self.sut.send(ENTER)
        self.sut.expect("run_simln", timeout=10)
        self.sut.send(DOWN)
        self.sut.send(DOWN)
        self.sut.send(DOWN)
        self.sut.send(DOWN)
        self.sut.send(DOWN)
        self.sut.send(DOWN)
        self.sut.send(DOWN)
        self.sut.send(DOWN)  # run_simln
        self.sut.send(ENTER)
        self.sut.expect("Sent command", timeout=60 * 3)
        self.sut.close()

        cmd = "warnet plugin run simln get_example_activity"
        self.log.info(cmd)
        self.sut = pexpect.spawn(cmd)
        self.sut.expect("amount_msat", timeout=10)
        self.sut.close()

        cmd = 'warnet plugin run simln launch_activity --params "$(warnet plugin run simln get_example_activity)"'
        self.log.info(f"/bin/bash -c '{cmd}'")
        self.sut = pexpect.spawn(f"/bin/bash -c '{cmd}'")
        self.sut.expect("install simln", timeout=10)
        self.sut.close()

        sleep(10)

    def copy_results(self) -> bool:
        self.log.info("Copying results")
        pod = get_pods_with_label("mission=simln")[0]
        self.wait_for_gossip_sync(2)
        wait_for_pod(pod.metadata.name, 60)
        sleep(20)

        log_resp = pod_log(pod.metadata.name, "simln")
        self.log.info(log_resp.data.decode("utf-8"))
        self.log.info("Sleep to process results")
        sleep(60)

        download(pod.metadata.name, Path("/working/results"), Path("."), pod.metadata.namespace)

        for root, _dirs, files in os.walk(Path("results")):
            for file_name in files:
                file_path = os.path.join(root, file_name)

                with open(file_path) as file:
                    content = file.read()
                    if "Success" in content:
                        return True
        return False

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


if __name__ == "__main__":
    test = SimLNTest()
    test.run_test()
