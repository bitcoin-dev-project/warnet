#!/usr/bin/env python3

import json
import os
from pathlib import Path

from test_base import TestBase

from warnet.services import ServiceType


class LNTest(TestBase):
    def __init__(self):
        super().__init__()
        self.graph_file_path = Path(os.path.dirname(__file__)) / "data" / "ln.graphml"

    def run_test(self):
        self.start_server()
        try:
            self.setup_network()
            self.run_ln_init_scenario()
            self.test_channel_policies()
            self.test_ln_payment_0_to_2()
            self.test_ln_payment_2_to_0()
            self.test_simln()
        finally:
            self.cleanup()

    def setup_network(self):
        self.log.info("Setting up network")
        self.log.info(self.warnet(f"network start {self.graph_file_path}"))
        self.wait_for_all_tanks_status(target="running")
        self.wait_for_all_edges()

    def get_cb_forwards(self, index):
        cmd = "wget -q -O - 127.0.0.1:9235/api/forwarding_history"
        res = self.wait_for_rpc(
            "exec_run", [index, ServiceType.CIRCUITBREAKER.value, cmd, self.network_name]
        )
        return json.loads(res)

    def run_ln_init_scenario(self):
        self.log.info("Running LN Init scenario")
        self.warnet("bitcoin rpc 0 getblockcount")
        self.warnet("scenarios run ln_init")
        self.wait_for_all_scenarios()
        scenario_return_code = self.get_scenario_return_code("ln_init")
        if scenario_return_code != 0:
            raise Exception("LN Init scenario failed")

    def test_channel_policies(self):
        self.log.info("Ensuring node-level channel policy settings")
        node2pub, node2host = json.loads(self.warnet("ln rpc 2 getinfo"))["uris"][0].split("@")
        chan_id = json.loads(self.warnet("ln rpc 2 listchannels"))["channels"][0]["chan_id"]
        chan = json.loads(self.warnet(f"ln rpc 2 getchaninfo {chan_id}"))

        # node_1 or node_2 is tank 2 with its non-default --bitcoin.timelockdelta=33
        if chan["node1_policy"]["time_lock_delta"] != 33:
            assert (
                chan["node2_policy"]["time_lock_delta"] == 33
            ), "Expected time_lock_delta to be 33"

        self.log.info("Ensuring no circuit breaker forwards yet")
        assert len(self.get_cb_forwards(1)["forwards"]) == 0, "Expected no circuit breaker forwards"

    def test_ln_payment_0_to_2(self):
        self.log.info("Test LN payment from 0 -> 2")
        inv = json.loads(self.warnet("ln rpc 2 addinvoice --amt=2000"))["payment_request"]
        self.log.info(f"Got invoice from node 2: {inv}")
        self.log.info("Paying invoice from node 0...")
        self.log.info(self.warnet(f"ln rpc 0 payinvoice -f {inv}"))

        self.wait_for_predicate(self.check_invoice_settled)

        self.log.info("Ensuring channel-level channel policy settings: source")
        payment = json.loads(self.warnet("ln rpc 0 listpayments"))["payments"][0]
        assert (
            payment["fee_msat"] == "5506"
        ), f"Expected fee_msat to be 5506, got {payment['fee_msat']}"

        self.log.info("Ensuring circuit breaker tracked payment")
        assert len(self.get_cb_forwards(1)["forwards"]) == 1, "Expected one circuit breaker forward"

    def test_ln_payment_2_to_0(self):
        self.log.info("Test LN payment from 2 -> 0")
        inv = json.loads(self.warnet("ln rpc 0 addinvoice --amt=1000"))["payment_request"]
        self.log.info(f"Got invoice from node 0: {inv}")
        self.log.info("Paying invoice from node 2...")
        self.log.info(self.warnet(f"ln rpc 2 payinvoice -f {inv}"))

        self.wait_for_predicate(lambda: self.check_invoices(0) == 1)

        self.log.info("Ensuring channel-level channel policy settings: target")
        payment = json.loads(self.warnet("ln rpc 2 listpayments"))["payments"][0]
        assert (
            payment["fee_msat"] == "2213"
        ), f"Expected fee_msat to be 2213, got {payment['fee_msat']}"

    def test_simln(self):
        self.log.info("Engaging simln")
        node2pub, _ = json.loads(self.warnet("ln rpc 2 getinfo"))["uris"][0].split("@")
        activity = [
            {"source": "ln-0", "destination": node2pub, "interval_secs": 1, "amount_msat": 2000}
        ]
        self.warnet(
            f"network export --exclude=[1] --activity={json.dumps(activity).replace(' ', '')}"
        )
        self.wait_for_predicate(lambda: self.check_invoices(2) > 1)
        assert self.check_invoices(0) == 1, "Expected one invoice for node 0"
        assert self.check_invoices(1) == 0, "Expected no invoices for node 1"

    def check_invoice_settled(self):
        invs = json.loads(self.warnet("ln rpc 2 listinvoices"))["invoices"]
        if len(invs) > 0 and invs[0]["state"] == "SETTLED":
            self.log.info("Invoice settled")
            return True
        return False

    def check_invoices(self, index):
        invs = json.loads(self.warnet(f"ln rpc {index} listinvoices"))["invoices"]
        settled = sum(1 for inv in invs if inv["state"] == "SETTLED")
        self.log.debug(f"Node {index} has {settled} settled invoices")
        return settled


if __name__ == "__main__":
    test = LNTest()
    test.run_test()
