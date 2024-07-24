#!/usr/bin/env python3

from time import sleep

from warnet.scenarios.utils import ensure_miner
from warnet.test_framework_bridge import WarnetTestFramework


def cli_help():
    return "Generate blocks over time. Options: [--allnodes | --interval=<number> | --mature ]"


class Miner:
    def __init__(self, node, mature):
        self.node = node
        self.wallet = ensure_miner(self.node)
        self.addr = self.wallet.getnewaddress()
        self.mature = mature


class MinerStd(WarnetTestFramework):
    def set_test_params(self):
        # This is just a minimum
        self.num_nodes = 0
        self.miners = []

    def add_options(self, parser):
        parser.add_argument(
            "--allnodes",
            dest="allnodes",
            action="store_true",
            help="When true, generate blocks from all nodes instead of just nodes[0]",
        )
        parser.add_argument(
            "--interval",
            dest="interval",
            default=60,
            type=int,
            help="Number of seconds between block generation (default 60 seconds)",
        )
        parser.add_argument(
            "--mature",
            dest="mature",
            action="store_true",
            help="When true, generate 101 blocks ONCE per miner",
        )

    def run_test(self):
        while not self.warnet.network_connected():
            self.log.info("Waiting for complete network connection...")
            sleep(5)
        self.log.info("Network connected. Starting miners.")

        max_miners = 1
        if self.options.allnodes:
            max_miners = len(self.nodes)
        for index in range(max_miners):
            self.miners.append(Miner(self.nodes[index], self.options.mature))

        while True:
            for miner in self.miners:
                num = 1
                if miner.mature:
                    num = 101
                    miner.mature = False
                try:
                    self.generatetoaddress(miner.node, num, miner.addr, sync_fun=self.no_op)
                    height = miner.node.getblockcount()
                    self.log.info(
                        f"generated {num} block(s) from node {miner.node.index}. New chain height: {height}"
                    )
                except Exception as e:
                    self.log.error(f"node {miner.node.index} error: {e}")
                sleep(self.options.interval)


if __name__ == "__main__":
    MinerStd().main()
