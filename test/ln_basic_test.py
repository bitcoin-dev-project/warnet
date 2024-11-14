#!/usr/bin/env python3

import json
import os
from pathlib import Path
from time import sleep

from test_base import TestBase


class LNBasicTest(TestBase):
    def __init__(self):
        super().__init__()
        self.network_dir = Path(os.path.dirname(__file__)) / "data" / "ln"
        self.scen_dir = Path(os.path.dirname(__file__)).parent / "resources" / "scenarios"
        self.lns = [
            "tank-0000-ln",
            "tank-0001-ln",
            "tank-0002-ln",
            "tank-0003-ln",
            "tank-0004-ln",
            "tank-0005-ln",
        ]

    def run_test(self):
        try:
            # Wait for all nodes to wake up
            self.setup_network()
            # Send money to all LN nodes
            self.fund_wallets()

            # Manually open two channels between first three nodes
            # and send a payment using warnet RPC
            self.manual_open_channels()
            self.wait_for_gossip_sync(self.lns[:3], 2)
            self.pay_invoice(sender="tank-0000-ln", recipient="tank-0002-ln")

            # Automatically open channels from network.yaml using warnet RPC
            self.automatic_open_channels()
            self.wait_for_gossip_sync(self.lns[3:], 2)
            # push_amt should enable payments from target to source
            self.pay_invoice(sender="tank-0005-ln", recipient="tank-0003-ln")

            # Automatically open channels from inside a scenario commander
            self.scenario_open_channels()
            self.pay_invoice(sender="tank-0002-ln", recipient="tank-0003-ln")

        finally:
            self.cleanup()

    def setup_network(self):
        self.log.info("Setting up network")
        self.log.info(self.warnet(f"deploy {self.network_dir}"))
        self.wait_for_all_tanks_status(target="running")

        self.warnet("bitcoin rpc tank-0000 createwallet miner")
        self.warnet("bitcoin rpc tank-0000 -generate 110")
        self.wait_for_predicate(
            lambda: int(self.warnet("bitcoin rpc tank-0000 getblockcount")) > 100
        )

        def wait_for_all_ln_rpc():
            for ln in self.lns:
                try:
                    self.warnet(f"ln rpc {ln} getinfo")
                except Exception:
                    print(f"LN node {ln} not ready for rpc yet")
                    return False
            return True

        self.wait_for_predicate(wait_for_all_ln_rpc)

    def fund_wallets(self):
        outputs = ""
        for lnd in self.lns:
            addr = json.loads(self.warnet(f"ln rpc {lnd} newaddress p2wkh"))["address"]
            outputs += f',"{addr}":10'
        # trim first comma
        outputs = outputs[1:]

        self.warnet("bitcoin rpc tank-0000 sendmany '' '{" + outputs + "}'")
        self.warnet("bitcoin rpc tank-0000 -generate 1")

    def wait_for_two_txs(self):
        self.wait_for_predicate(
            lambda: json.loads(self.warnet("bitcoin rpc tank-0000 getmempoolinfo"))["size"] == 2
        )

    def manual_open_channels(self):
        # 0 -> 1 -> 2
        pk1 = self.warnet("ln pubkey tank-0001-ln")
        pk2 = self.warnet("ln pubkey tank-0002-ln")

        host1 = ""
        host2 = ""

        while not host1 or not host2:
            if not host1:
                host1 = self.warnet("ln host tank-0001-ln")
            if not host2:
                host2 = self.warnet("ln host tank-0002-ln")
            sleep(1)

        print(
            self.warnet(
                f"ln rpc tank-0000-ln openchannel --node_key {pk1} --local_amt 100000 --connect {host1}"
            )
        )
        print(
            self.warnet(
                f"ln rpc tank-0001-ln openchannel --node_key {pk2} --local_amt 100000 --connect {host2}"
            )
        )

        self.wait_for_two_txs()

        self.warnet("bitcoin rpc tank-0000 -generate 10")

    def wait_for_gossip_sync(self, nodes, expected):
        while len(nodes) > 0:
            for node in nodes:
                chs = json.loads(self.warnet(f"ln rpc {node} describegraph"))["edges"]
                if len(chs) >= expected:
                    nodes.remove(node)
            sleep(1)

    def pay_invoice(self, sender: str, recipient: str):
        init_balance = int(json.loads(self.warnet(f"ln rpc {recipient} channelbalance"))["balance"])
        inv = json.loads(self.warnet(f"ln rpc {recipient} addinvoice --amt 1000"))
        print(inv)
        print(self.warnet(f"ln rpc {sender} payinvoice -f {inv['payment_request']}"))

        def wait_for_success():
            return (
                int(json.loads(self.warnet(f"ln rpc {recipient} channelbalance"))["balance"])
                == init_balance + 1000
            )

        self.wait_for_predicate(wait_for_success)

    def automatic_open_channels(self):
        # 3 -> 4 -> 5
        self.warnet("ln open-all-channels")

        self.wait_for_two_txs()

        self.warnet("bitcoin rpc tank-0000 -generate 10")

    def scenario_open_channels(self):
        # 2 -> 3
        # connecting all six ln nodes in the graph
        scenario_file = self.scen_dir / "test_scenarios" / "ln_basic.py"
        self.log.info(f"Running scenario from: {scenario_file}")
        self.warnet(f"run {scenario_file} --source_dir={self.scen_dir} --debug")


if __name__ == "__main__":
    test = LNBasicTest()
    test.run_test()
