#!/usr/bin/env python3
import asyncio
import random
from datetime import datetime

from warnet.test_framework_bridge import WarnetTestFramework
from scenarios.utils import ensure_miner, next_block_delta
from test_framework.test_node import TestNode
import concurrent.futures
from threading import Lock


BLOCKS_WAIT_TILL_SPENDABLE = 101
AVERAGE_BLOCK_TIME = 60


def cli_help():
    return "Scenario: Double TX Relay"


class DoubleTXRelay(WarnetTestFramework):
    def set_test_params(self):
        self.num_nodes = 1

    def add_options(self, parser):
        parser.add_argument(
            "--txproductionrate",
            dest="txproductionrate",
            default=5,
            # action="store_true",
            help="Rate per second at which transactions are generated. (default 5 tx/s)",
        )
        parser.add_argument(
            "--speedyinitialblockrewards",
            dest="speedyinitialblockrewards",
            default=True,
            type=bool,
            help="Mines blocks quickly at first to get the first rewards available. (default True)",
        )

    def enqueue_block(self, node: TestNode):
        self.block_queue.append((node))

    def dequeue_spendable_block_if_available(self):
        if len(self.block_queue) < BLOCKS_WAIT_TILL_SPENDABLE:
            return None
        return self.block_queue.pop(0)

    def run_test(self):
        self.log.info("Starting Double TX Relay Scenario")
        self.block_queue = []
        self.mutex = Lock()
        self.sent_txs = 0  # protected by mutex
        self.time_of_last_log = datetime.now()  # protected by mutex

        network_size = len(self.nodes)

        if self.options.speedyinitialblockrewards:
            self.log.info("Generating initial blocks and rewards")
            for node in self.nodes:
                self.generate_block(node)
            for _ in range(BLOCKS_WAIT_TILL_SPENDABLE):
                self.generate_block(self.nodes[0])

        self.log.info("Starting block mining and tx sending in real time")

        # asyncio.run(self.mainasync())

        # for b in range(BLOCKS):
        #     for t in range(TXS):
        #         txid = self.nodes[0].sendtoaddress(address=addr, amount=0.001)
        #         self.log.info(f"sending tx {t}/{TXS}: {txid}")
        #     block = self.generate(self.nodes[0], 1)
        #     self.log.info(f"generating block {b}/{BLOCKS}: {block}")

    def generate_block(self, node: TestNode):
        try:
            self.log.info("Generating block for node: %s", node.index)
            wallet = ensure_miner(node)
            addr = wallet.getnewaddress(address_type="bech32m")
            _ = self.generatetoaddress(node, 1, addr)
            self.enqueue_block(node)
            node_with_spendable_block = self.dequeue_spendable_block_if_available()
            if node_with_spendable_block is not None:
                self.split_block_up(node_with_spendable_block)
        except Exception as e:
            self.log.error("Error generating block: %s", e)

    def split_block_up(self, node: TestNode):
        try:
            self.log.info("Splitting block up for node: %s", node.index)
            wallet = ensure_miner(node)
            addresses = {}
            for _ in range(499):
                addresses[wallet.getnewaddress(address_type="bech32m")] = 0.1
            node.send(outputs=addresses)
        except Exception as e:
            self.log.error("Error splitting block up: %s", e)

    async def mainasync(self):
        await asyncio.gather(self.mineblocks(), self.sendtransactions())

    async def mineblocks(self):
        print(
            f"Starting process to select a random node to mine a block roughly every {AVERAGE_BLOCK_TIME} seconds"
        )
        while True:
            try:
                # trunk-ignore(bandit/B311)
                node = random.choice(self.nodes)
                self.generate_block(node)
                delay = next_block_delta(AVERAGE_BLOCK_TIME)
                self.log.info(f"Waiting {'%.0f' % delay} seconds to mine next block")
                await asyncio.sleep(delay)
            except Exception as e:
                self.log.error("Error mining blocks: %s", e)
                await asyncio.sleep(10)

    async def sendtransactions(self):
        print(
            f"Starting process to send transactions at a rate of {self.options.txproductionrate} tx/s"
        )
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            while True:
                executor.submit(self.send_transaction)
                await asyncio.sleep(1 / int(self.options.txproductionrate))

    def send_transaction(self):
        try:
            # trunk-ignore(bandit/B311)
            from_node = random.choice(self.nodes)
            # trunk-ignore(bandit/B311)
            to_node = random.choice(self.nodes)
            from_node.send(outputs={to_node.getnewaddress(address_type="bech32m"): 0.09999889})
            # runs in thread pool so mutex is needed
            with self.mutex:
                self.sent_txs += 1
                seconds_since_log = (datetime.now() - self.time_of_last_log).total_seconds()
                if seconds_since_log > 59:
                    self.log.info(
                        f"Sent roughly {'%.2f' % (self.sent_txs / 60)} transactions per second over the last minute"
                    )
                    self.sent_txs = 0
                    self.time_of_last_log = datetime.now()
        except Exception as e:
            self.log.error("Error sending transaction: %s", e)


# bcli -rpcwallet=test-wallet -named send outputs="{\"$ADDRESS\": 1}" fee_rate=10

if __name__ == "__main__":
    print("Running Double TX Relay Scenario")
    DoubleTXRelay().main()
