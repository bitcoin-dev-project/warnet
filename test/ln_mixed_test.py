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
            CLN("tank-0001-cln", self.log),
            CLN("tank-0002-cln", self.log),
            LND("tank-0003-lnd", self.log),
            LND("tank-0004-lnd", self.log),
            LND("tank-0005-lnd", self.log),
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
            self.pay_invoice_rpc(sender="tank-0003-lnd", recipient="tank-0001-cln")
            # self.pay_invoice_node(sender="tank-0001-cln", recipient="tank-0003-lnd")

            # Manually open more channels between first three nodes
            # and send a payment using warnet RPC
            self.manual_open_channels()
            # FIXME: need to decide how to interact with LND via REST outside cluster
            # self.wait_for_gossip_sync(self.lns, 5)
            # self.pay_invoice(sender="tank-0004-lnd", recipient="tank-0002-cln")

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
        pk1 = self.warnet("ln pubkey tank-0004-lnd")  # prefer -> self.node("tank-0004-lnd").uri()
        cln1_lnd4_channel = self.node("tank-0001-cln").channel(pk1, 444444, 200000, 5000)
        assert "txid" in cln1_lnd4_channel, "Failed to create channel between CLN and LND"
        print(cln1_lnd4_channel["txid"])

        # 4 -> 2
        # lnd4_cln2_channel = self.node("tank-0004-lnd").channel(
        #     self.lns[1].uri(), 333333, 150000, 5000
        # )
        # assert "txid" in lnd4_cln2_channel, "Failed to create channel between LND and CLN"
        # print(lnd4_cln2_channel["txid"])

        self.wait_for_txs(1)

        self.warnet("bitcoin rpc tank-0001 -generate 10")

    def wait_for_gossip_sync(self, nodes, expected):
        while len(nodes) > 0:
            for node in nodes:
                chs = node.graph()["edges"]
                if len(chs) >= expected:
                    print(f"Too many edges for {node}")
            sleep(1)

    def pay_invoice_rpc(self, sender: str, recipient: str):
        print("pay invoice using ln rpc")
        init_balance = self.node(recipient).channelbalance()
        print("initial balance", init_balance)
        # create cln invoice
        inv = json.loads(self.warnet(f"ln rpc {recipient} invoice 1000000 label description"))
        print(inv)
        # pay from lightning
        print(self.warnet(f"ln rpc {sender} payinvoice -f {inv['bolt11']}"))

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
