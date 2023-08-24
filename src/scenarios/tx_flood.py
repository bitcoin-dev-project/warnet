#!/usr/bin/env python3

import logging
from test_framework.test_framework import BitcoinTestFramework
from scenarios.utils import ensure_miner

BLOCKS = 100
TXS = 100


def cli_help():
    return ("Generate 100 blocks with 100 TXs each")


class TXFlood(BitcoinTestFramework):
    def set_test_params(self):
        pass

    def run_test(self):
        miner = ensure_miner(self.nodes[0])
        addr = miner.getnewaddress()
        self.generatetoaddress(self.nodes[0], 200, addr)
        for b in range(BLOCKS):
            for t in range(TXS):
                txid = self.nodes[0].sendtoaddress(address=addr, amount=0.001)
                logging.debug(f"sending tx {t}/{TXS}: {txid}")
            block = self.generate(self.nodes[0], 1)
            logging.debug(f"generating block {b}/{BLOCKS}: {block}")


if __name__ == '__main__':
    TXFlood().main()

