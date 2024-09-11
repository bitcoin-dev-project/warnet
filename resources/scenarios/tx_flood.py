#!/usr/bin/env python3
import threading
from random import choice, randrange
from time import sleep

# The base class exists inside the commander container
try:
    from commander import Commander
except ImportError:
    from resources.scenarios.commander import Commander


class TXFlood(Commander):
    def set_test_params(self):
        self.num_nodes = 1
        self.addrs = []
        self.threads = []

    def add_options(self, parser):
        parser.description = (
            "Sends random transactions between all nodes with available balance in their wallet"
        )
        parser.usage = "warnet run /path/to/tx_flood.py [options]"
        parser.add_argument(
            "--interval",
            dest="interval",
            default=10,
            type=int,
            help="Number of seconds between TX generation (default 10 seconds)",
        )

    def orders(self, node):
        wallet = self.ensure_miner(node)
        for address_type in ["legacy", "p2sh-segwit", "bech32", "bech32m"]:
            self.addrs.append(wallet.getnewaddress(address_type=address_type))
        while True:
            sleep(self.options.interval)
            try:
                bal = wallet.getbalance()
                if bal < 1:
                    continue
                amounts = {}
                num_out = randrange(1, (len(self.nodes) // 2) + 1)
                for _ in range(num_out):
                    sats = int(float((bal / 20) / num_out) * 1e8)
                    amounts[choice(self.addrs)] = randrange(sats // 4, sats) / 1e8
                wallet.sendmany(dummy="", amounts=amounts)
                self.log.info(f"node {node.index} sent tx with {num_out} outputs")
            except Exception as e:
                self.log.error(f"node {node.index} error: {e}")

    def run_test(self):
        self.log.info(f"Starting TX mess with {len(self.nodes)} threads")
        for node in self.nodes:
            sleep(1)  # stagger
            t = threading.Thread(target=lambda n=node: self.orders(n))
            t.daemon = False
            t.start()
            self.threads.append({"thread": t, "node": node})

        while len(self.threads) > 0:
            for thread in self.threads:
                if not thread["thread"].is_alive():
                    self.log.info(f"restarting thread for node {thread['node'].index}")
                    thread["thread"] = threading.Thread(
                        target=lambda n=thread["node"]: self.orders(n)
                    )
                    thread["thread"].daemon = False
                    thread["thread"].start()
            sleep(30)


if __name__ == "__main__":
    TXFlood().main()
