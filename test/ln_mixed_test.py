#!/usr/bin/env python3

import json
import os
from pathlib import Path
from time import sleep

from test_base import TestBase

from resources.scenarios.ln_framework.ln import CLN, ECLAIR, LND, LNNode
from warnet.process import stream_command


class LNMultiTest(TestBase):
    def __init__(self):
        super().__init__()
        self.network_dir = Path(os.path.dirname(__file__)) / "data" / "ln_mixed"
        self.scen_dir = Path(os.path.dirname(__file__)).parent / "resources" / "scenarios"
        self.lns = [
            ECLAIR("tank-0001-ln", use_rpc=True),
            CLN("tank-0002-ln", use_rpc=True),
            LND("tank-0003-ln", use_rpc=True),
            LND("tank-0004-ln", use_rpc=True),
            LND("tank-0005-ln", use_rpc=True),
        ]

    def node(self, name: str) -> LNNode:
        matching_nodes = [n for n in self.lns if n.name == name]
        if not matching_nodes:
            raise ValueError(f"No node found with name: {name}")
        return matching_nodes[0]

    def run_test(self):
        try:
            # Wait for all nodes to wake up. ln_init will start automatically
            self.setup_network()

            # open channel and pay invoice
            self.manual_open_channels()
            self.pay_invoice(sender="tank-0003-ln", recipient="tank-0004-ln")

            # pay cln to lnd - channel opened by ln_init - test routing
            self.pay_invoice(sender="tank-0002-ln", recipient="tank-0003-ln")

            # pay lnd to eclair - channel opened by ln_init - test routing 3 -> 1
            self.pay_invoice(sender="tank-0003-ln", recipient="tank-0001-ln")

        finally:
            self.cleanup()

    def setup_network(self):
        self.log.info("Setting up network")
        stream_command(f"warnet deploy {self.network_dir}")

    def wait_for_txs(self, count):
        self.wait_for_predicate(
            lambda: json.loads(self.warnet("bitcoin rpc tank-0001 getmempoolinfo"))["size"] == count
        )

    def manual_open_channels(self):
        # 3 -> 4
        pk4 = self.node("tank-0004-ln").nodeid()
        channel = self.node("tank-0003-ln").channel(pk4, "444444", "200000", "5000", 1)
        assert "txid" in channel, "Failed to create channel between nodes"
        self.log.info(f"Channel txid {channel['txid']}")

        self.wait_for_txs(1)

        self.warnet("bitcoin rpc tank-0001 -generate 10")

    def wait_for_gossip_sync(self, nodes, expected):
        while len(nodes) > 0:
            for node in nodes:
                chs = node.graph()["edges"]
                if len(chs) >= expected:
                    self.log.info(f"Too many edges for {node}")
            sleep(1)

    def pay_invoice(self, sender: str, recipient: str):
        self.log.info(f"pay invoice using LNNode {sender} -> {recipient}")
        init_balance = self.node(recipient).channelbalance()
        assert init_balance > 0, f"{recipient} is zero, abort"

        self.log.info(f"{recipient} initial balance {init_balance}")

        # create invoice
        inv = self.node(recipient).createinvoice(10000, f"{sender}-{recipient}")
        self.log.info(f"invoice {inv}")
        # pay recipient invoice
        self.log.info(self.node(sender).payinvoice(inv))

        def wait_for_success():
            current_balance = self.node(recipient).channelbalance()
            self.log.info(f"{recipient} current balance {current_balance}")
            return current_balance == init_balance + 10000

        self.wait_for_predicate(wait_for_success)


if __name__ == "__main__":
    test = LNMultiTest()
    test.run_test()
