#!/usr/bin/env python3

import json
import os
from pathlib import Path
from time import sleep

from test_base import TestBase

from resources.scenarios.ln_framework.ln import CLN, LND, LNNode
from warnet.process import stream_command


class LNMultiTest(TestBase):
    def __init__(self):
        super().__init__()
        self.network_dir = Path(os.path.dirname(__file__)) / "data" / "ln_mixed"
        self.scen_dir = Path(os.path.dirname(__file__)).parent / "resources" / "scenarios"
        self.lns = [
            CLN("tank-0001-ln"),
            CLN("tank-0002-ln"),
            LND("tank-0003-ln"),
            LND("tank-0004-ln"),
            LND("tank-0005-ln"),
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

            assert self.lns[0].walletbalance() > 0, (
                f"{self.lns[0]} has does not have a wallet balance"
            )
            # Send a payment across channels opened automatically by ln_init
            self.pay_invoice_rpc(sender="tank-0003-ln", recipient="tank-0001-ln")
            # self.pay_invoice_node(sender="tank-0001-ln", recipient="tank-0003-ln")

            # Manually open more channels between first three nodes
            # and send a payment using warnet RPC
            self.manual_open_channels()
            # FIXME: need to decide how to interact with LND via REST outside cluster
            # self.wait_for_gossip_sync(self.lns, 5)
            # self.pay_invoice(sender="tank-0004-ln", recipient="tank-0002-ln")

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
        # 1 -> 4
        pk1 = self.warnet("ln pubkey tank-0004-ln")  # prefer -> self.node("tank-0004-ln").uri()
        channel = self.node("tank-0001-ln").channel(pk1, 444444, 200000, 5000)
        assert "txid" in channel, "Failed to create channel between CLN and LND"
        self.log.info(f"Channel txid {channel['txid']}")

        # 4 -> 2
        # channel = self.node("tank-0004-ln").channel(
        #     self.lns[1].uri(), 333333, 150000, 5000
        # )
        # assert "txid" in channel, "Failed to create channel between LND and CLN"
        # self.log.info(f'Channel txid {channel["txid"]}')

        self.wait_for_txs(1)

        self.warnet("bitcoin rpc tank-0001 -generate 10")

    def wait_for_gossip_sync(self, nodes, expected):
        while len(nodes) > 0:
            for node in nodes:
                chs = node.graph()["edges"]
                if len(chs) >= expected:
                    self.log.info(f"Too many edges for {node}")
            sleep(1)

    def pay_invoice_rpc(self, sender: str, recipient: str):
        self.log.info("pay invoice using ln rpc")
        init_balance = self.node(recipient).channelbalance()
        self.log.info(f"initial balance {init_balance}")
        # create cln invoice
        inv = json.loads(self.warnet(f"ln rpc {recipient} invoice 1000000 label description"))
        self.log.info(inv)
        # pay from lightning
        self.log.info(self.warnet(f"ln rpc {sender} payinvoice -f {inv['bolt11']}"))

        def wait_for_success():
            return self.node(recipient).channelbalance() == init_balance + 1000

        self.wait_for_predicate(wait_for_success)

    # def pay_invoice_node(self, sender: str, recipient: str):
    #     print("pay invoice using ln framework")
    #     #FIXME: LND Node is not accessible outside the cluster
    #     init_balance = self.node(recipient).channelbalance()
    #     print("initial balance", init_balance)
    #     # create invoice
    #     inv = self.node(recipient).createinvoice(1000, "label2")
    #     print(inv)
    #     # pay invoie
    #     print(self.node(sender).payinvoice(inv))

    #     def wait_for_success():
    #         print(self.node(recipient).channelbalance())
    #         return self.node(recipient).channelbalance() == init_balance + 1000

    #     self.wait_for_predicate(wait_for_success)


if __name__ == "__main__":
    test = LNMultiTest()
    test.run_test()
