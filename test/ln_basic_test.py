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
        self.miner_addr = ""

    def run_test(self):
        try:
            self.setup_network()
            self.fund_wallets()
            self.manual_open_channels()
            self.wait_for_gossip_sync()
            self.pay_invoice()
        finally:
            self.cleanup()

    def setup_network(self):
        self.log.info("Setting up network")
        self.log.info(self.warnet(f"deploy {self.network_dir}"))
        self.wait_for_all_tanks_status(target="running")

    def fund_wallets(self):
        self.warnet("bitcoin rpc tank-0000 createwallet miner")
        self.warnet("bitcoin rpc tank-0000 -generate 110")
        self.wait_for_predicate(
            lambda: int(self.warnet("bitcoin rpc tank-0000 getblockcount")) > 100
        )

        addrs = []
        for lnd in ["tank-0000-lnd", "tank-0001-lnd", "tank-0002-lnd"]:
            addrs.append(json.loads(self.warnet(f"ln rpc {lnd} newaddress p2wkh"))["address"])

        self.warnet(
            "bitcoin rpc tank-0000 sendmany '' '{"
            + f'"{addrs[0]}":10,"{addrs[1]}":10,"{addrs[2]}":10'
            + "}'"
        )
        self.warnet("bitcoin rpc tank-0000 -generate 1")

    def manual_open_channels(self):
        # 0 -> 1 -> 2
        pk1 = self.warnet("ln pubkey tank-0001-lnd")
        pk2 = self.warnet("ln pubkey tank-0002-lnd")

        host1 = None
        host2 = None

        while not host1 or not host2:
            if not host1:
                host1 = self.warnet("ln host tank-0001-lnd")
            if not host2:
                host2 = self.warnet("ln host tank-0002-lnd")
            sleep(1)

        print(
            self.warnet(
                f"ln rpc tank-0000-lnd openchannel --node_key {pk1} --local_amt 100000 --connect {host1}"
            )
        )
        print(
            self.warnet(
                f"ln rpc tank-0001-lnd openchannel --node_key {pk2} --local_amt 100000 --connect {host2}"
            )
        )

        def wait_for_two_txs():
            return json.loads(self.warnet("bitcoin rpc tank-0000 getmempoolinfo"))["size"] == 2

        self.wait_for_predicate(wait_for_two_txs)

        self.warnet("bitcoin rpc tank-0000 -generate 10")

    def wait_for_gossip_sync(self):
        chs0 = []
        chs1 = []
        chs2 = []

        while len(chs0) != 2 or len(chs1) != 2 or len(chs2) != 2:
            if len(chs0) != 2:
                chs0 = json.loads(self.warnet("ln rpc tank-0000-lnd describegraph"))["edges"]
            if len(chs1) != 2:
                chs1 = json.loads(self.warnet("ln rpc tank-0001-lnd describegraph"))["edges"]
            if len(chs2) != 2:
                chs2 = json.loads(self.warnet("ln rpc tank-0002-lnd describegraph"))["edges"]
            sleep(1)

    def pay_invoice(self):
        inv = json.loads(self.warnet("ln rpc tank-0002-lnd addinvoice --amt 1000"))
        print(inv)
        print(self.warnet(f"ln rpc tank-0000-lnd payinvoice -f {inv['payment_request']}"))

        def wait_for_success():
            return json.loads(self.warnet("ln rpc tank-0002-lnd channelbalance"))["balance"] == 1000
            self.wait_for_predicate(wait_for_success)


if __name__ == "__main__":
    test = LNBasicTest()
    test.run_test()
