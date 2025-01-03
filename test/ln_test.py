#!/usr/bin/env python3
import ast
import json
import os
from pathlib import Path
from typing import Optional

from test_base import TestBase

from warnet.k8s import wait_for_pod
from warnet.process import run_command, stream_command


class LNTest(TestBase):
    def __init__(self):
        super().__init__()
        self.graph_file = Path(os.path.dirname(__file__)) / "data" / "LN_10.json"
        self.imported_network_dir = self.tmpdir / "imported_network"
        self.scen_dir = Path(os.path.dirname(__file__)).parent / "resources" / "scenarios"
        self.plugins_dir = Path(os.path.dirname(__file__)).parent / "resources" / "plugins"
        self.simln_exec = Path("simln/plugin.py")

    def run_test(self):
        try:
            self.import_network()
            self.setup_network()
            self.test_channel_policies()
            self.test_payments()
            self.run_simln()
        finally:
            self.cleanup()

    def import_network(self):
        self.log.info("Importing network graph from JSON...")
        res = self.warnet(f"import-network {self.graph_file} {self.imported_network_dir}")
        self.log.info(f"\n{res}")

    def setup_network(self):
        self.log.info("Setting up network...")
        stream_command(f"warnet deploy {self.imported_network_dir}")

    def test_channel_policies(self):
        self.log.info("Ensuring node-level channel policy settings")
        graphs = []
        for n in range(10):
            ln = f"tank-{n:04d}-ln"
            res = self.warnet(f"ln rpc {ln} describegraph")
            graphs.append(json.loads(res)["edges"])

        def check_policy(node: int, index: int, field: str, values: tuple):
            self.log.info(f"Checking policy: Node={node} ch={index} Expected={field}:{values}")
            graph = graphs[node]
            assert len(graph) == 13
            ch = graph[index]
            a = int(ch["node1_policy"][field])
            b = int(ch["node2_policy"][field])
            assert values == (a, b) or values == (
                b,
                a,
            ), f"policy check failed:\nActual:\n{ch}\nExpected:\n{field}:{values}"

        # test one property of one channel from each node
        check_policy(0, 0, "fee_base_msat", (250, 1000))
        check_policy(1, 1, "time_lock_delta", (40, 100))
        check_policy(2, 2, "fee_rate_milli_msat", (1, 4000))
        check_policy(3, 3, "fee_rate_milli_msat", (499, 4000))
        check_policy(4, 4, "time_lock_delta", (40, 144))
        check_policy(5, 5, "max_htlc_msat", (1980000000, 1500000000))
        check_policy(6, 6, "fee_rate_milli_msat", (550, 71))
        check_policy(7, 7, "min_htlc", (1000, 1))
        check_policy(8, 8, "time_lock_delta", (80, 144))
        check_policy(9, 9, "fee_base_msat", (616, 1000))

    def test_payments(self):
        def get_and_pay(src, tgt):
            src = f"tank-{src:04d}-ln"
            tgt = f"tank-{tgt:04d}-ln"
            invoice = json.loads(self.warnet(f"ln rpc {tgt} addinvoice --amt 230118"))[
                "payment_request"
            ]
            print(self.warnet(f"ln rpc {src} payinvoice {invoice} --force"))

        get_and_pay(0, 5)
        get_and_pay(2, 3)
        get_and_pay(1, 9)
        get_and_pay(8, 7)
        get_and_pay(4, 6)

    def run_simln(self):
        self.log.info("Running SimLN...")
        activity_cmd = f"{self.plugins_dir}/{self.simln_exec} get-example-activity"
        activity = run_command(activity_cmd)
        launch_cmd = f"{self.plugins_dir}/{self.simln_exec} launch-activity '{activity}'"
        pod = run_command(launch_cmd).strip()
        wait_for_pod(pod)
        self.log.info("Checking SimLN...")
        self.wait_for_predicate(self.found_results_remotely)
        self.log.info("SimLN was successful.")

    def found_results_remotely(self, pod: Optional[str] = None) -> bool:
        if pod is None:
            pod = self.get_first_simln_pod()
        self.log.info(f"Checking for results file in {pod}")
        results_file = run_command(
            f"{self.plugins_dir}/{self.simln_exec} sh {pod} ls /working/results"
        ).strip()
        self.log.info(f"Results file: {results_file}")
        results = run_command(
            f"{self.plugins_dir}/{self.simln_exec} sh {pod} cat /working/results/{results_file}"
        ).strip()
        self.log.info(results)
        return results.find("Success") > 0

    def get_first_simln_pod(self):
        command = f"{self.plugins_dir}/{self.simln_exec} list-pod-names"
        pod_names_literal = run_command(command)
        self.log.info(f"{command}: {pod_names_literal}")
        pod_names = ast.literal_eval(pod_names_literal)
        return pod_names[0]


if __name__ == "__main__":
    test = LNTest()
    test.run_test()
