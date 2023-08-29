#!/usr/bin/env python3

from warnet.test_framework_bridge import WarnetTestFramework
from scenarios.utils import ensure_miner

BLOCKS = 100
TXS = 100


def cli_help():
    return "Generate 100 blocks with 100 TXs each"


class TXFlood(WarnetTestFramework):
    def set_test_params(self):
        self.num_nodes = 1

    def run_test(self):
        miner = ensure_miner(self.nodes[0])
        addr = miner.getnewaddress()
        self.generatetoaddress(self.nodes[0], 200, addr)
        for b in range(BLOCKS):
            for t in range(TXS):
                txid = self.nodes[0].sendtoaddress(address=addr, amount=0.001)
                self.log.info(f"sending tx {t}/{TXS}: {txid}")
            block = self.generate(self.nodes[0], 1)
            self.log.info(f"generating block {b}/{BLOCKS}: {block}")


if __name__ == "__main__":
    TXFlood().main()
