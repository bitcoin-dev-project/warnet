#!/usr/bin/env python3
import threading
from random import randrange, choice
from time import sleep
from scenarios.utils import ensure_miner
from warnet.test_framework_bridge import WarnetTestFramework

BLOCKS = 100
TXS = 100


def cli_help():
    return "Make a big transaction mess"


class TXFlood(WarnetTestFramework):
    def set_test_params(self):
        self.num_nodes = 1
        self.addrs = []
        self.threads = []

    def orders(self, node):
        try:
            wallet = ensure_miner(node)
            for address_type in ["legacy", "p2sh-segwit", "bech32", "bech32m"]:
                self.addrs.append(wallet.getnewaddress(address_type=address_type))
            while True:
                sleep(1)
                bal = wallet.getbalance()
                self.log.info(f"node {node.index} balance: {bal}")
                if bal < 1:
                    continue
                amounts = {}
                num_out = randrange(1, len(self.nodes) // 2)
                for _ in range(num_out):
                    sats = int(float((bal / 2) / num_out) * 1e8)
                    amounts[choice(self.addrs)] = randrange(sats // 4, sats) / 1e8
                wallet.sendmany(dummy="", amounts=amounts)
                self.log.info(f"node {node.index} sendmany:\n  {amounts}")
        except Exception as e:
            self.log.error(f"thread for node {node.index} crashed: {e}")

    def run_test(self):
        self.log.info(f"Starting TX mess with {len(self.nodes)} threads")
        for node in self.nodes:
            t = threading.Thread(target=lambda: self.orders(node))
            t.daemon = False
            t.start()
            self.threads.append({"thread": t, "node": node})

        while len(self.threads) > 0:
            for thread in self.threads:
                if not thread["thread"].is_alive():
                    self.log.info(f"restarting thread for node {thread['node'].index}")
                    thread["thread"] = threading.Thread(target=lambda: self.orders(thread["node"]))
                    thread["thread"].daemon = False
                    thread["thread"].start()
            sleep(30)

if __name__ == "__main__":
    TXFlood().main()
