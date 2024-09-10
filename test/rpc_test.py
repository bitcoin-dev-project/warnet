#!/usr/bin/env python3

import json
import os
from pathlib import Path

from test_base import TestBase


class RPCTest(TestBase):
    def __init__(self):
        super().__init__()
        self.network_dir = Path(os.path.dirname(__file__)) / "data" / "12_node_ring"

    def run_test(self):
        try:
            self.setup_network()
            self.test_rpc_commands()
            self.test_transaction_propagation()
            self.test_message_exchange()
            self.test_address_manager()
        finally:
            self.cleanup()

    def setup_network(self):
        self.log.info("Setting up network")
        self.log.info(self.warnet(f"deploy {self.network_dir}"))
        self.wait_for_all_tanks_status(target="running")
        self.wait_for_all_edges()

    def test_rpc_commands(self):
        self.log.info("Testing basic RPC commands")
        self.warnet("bitcoin rpc tank-0000 getblockcount")
        self.warnet("bitcoin rpc tank-0001 createwallet miner")
        self.warnet("bitcoin rpc tank-0001 -generate 101")
        self.wait_for_predicate(lambda: "101" in self.warnet("bitcoin rpc tank-0000 getblockcount"))

    def test_transaction_propagation(self):
        self.log.info("Testing transaction propagation")
        address = "bcrt1qthmht0k2qnh3wy7336z05lu2km7emzfpm3wg46"
        txid = self.warnet(f"bitcoin rpc tank-0001 sendtoaddress {address} 0.1")
        self.wait_for_predicate(lambda: txid in self.warnet("bitcoin rpc tank-0000 getrawmempool"))

        node_log = self.warnet("bitcoin debug-log tank-0001")
        assert txid in node_log, "Transaction ID not found in node log"

        all_logs = self.warnet(f"bitcoin grep-logs {txid}")
        count = all_logs.count("Enqueuing TransactionAddedToMempool")
        assert count > 1, f"Transaction not propagated to enough nodes (count: {count})"

    def test_message_exchange(self):
        self.log.info("Testing message exchange between nodes")
        msgs = self.warnet("bitcoin messages tank-0000 tank-0001")
        assert "verack" in msgs, "VERACK message not found in exchange"

    def test_address_manager(self):
        self.log.info("Testing address manager")

        def got_addrs():
            addrman = json.loads(self.warnet("bitcoin rpc tank-0000 getrawaddrman"))
            for key in ["tried", "new"]:
                obj = addrman[key]
                keys = list(obj.keys())
                groups = [g.split("/")[0] for g in keys]
                if len(set(groups)) > 1:
                    return True
            return False

        self.wait_for_predicate(got_addrs)


if __name__ == "__main__":
    test = RPCTest()
    test.run_test()
