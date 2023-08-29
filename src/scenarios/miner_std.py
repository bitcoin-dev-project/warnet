#!/usr/bin/env python3

from time import sleep
from warnet.test_framework_bridge import WarnetTestFramework
from scenarios.utils import ensure_miner


def cli_help():
    return "Generate blocks over time. Options: [--allnodes | --interval=<number>]"


class MinerStd(WarnetTestFramework):
    def set_test_params(self):
        # This is just a minimum
        self.num_nodes = 0

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

    def run_test(self):
        current_miner = 0

        while True:
            miner = ensure_miner(self.nodes[current_miner])
            addr = miner.getnewaddress()
            block = self.generatetoaddress(self.nodes[current_miner], 1, addr)
            self.log.info(f"generated block from node {current_miner}: {block}")
            if self.options.allnodes:
                current_miner = current_miner + 1
                if current_miner >= self.num_nodes:
                    current_miner = 0
            sleep(self.options.interval)


if __name__ == "__main__":
    MinerStd().main()
