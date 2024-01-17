#!/usr/bin/env python3
import asyncio
import random
import math
from datetime import datetime
from decimal import Decimal

from warnet.test_framework_bridge import WarnetTestFramework
from scenarios.utils import ensure_miner, next_block_delta, get_block_reward_sats
from test_framework.test_node import TestNode
import concurrent.futures
from threading import Lock


BLOCKS_WAIT_TILL_SPENDABLE = 101
MIN_UTXO_AMOUNT = Decimal(0.001)
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

    def enqueue_block(self, block_and_node):
        self.block_queue.append(block_and_node)

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
        self.failed_txs = 0  # protected by mutex

        if self.options.speedyinitialblockrewards:
            self.log.info("Generating initial blocks and rewards")
            for node in self.nodes:
                self.generate_block(self.nodes[0], node)
            for _ in range(BLOCKS_WAIT_TILL_SPENDABLE):
                self.generate_block(self.nodes[0], self.nodes[0])

        self.log.info("Starting block mining and tx sending in real time")

        asyncio.run(self.mainasync())

    def generate_block(self, generating_node: TestNode, receiving_node: TestNode):
        try:
            self.log.info("Generating block for node: %s", receiving_node.index)
            wallet = ensure_miner(receiving_node)
            addr = wallet.getnewaddress(address_type="bech32m")
            block = self.generatetoaddress(generating_node, 1, addr)[0]
            self.enqueue_block((block, receiving_node))
            spendable_block_and_node = self.dequeue_spendable_block_if_available()
            if spendable_block_and_node is not None:
                self.split_block_up(spendable_block_and_node)
        except Exception as e:
            self.log.error("Error generating block: %s", e)

    def split_block_up(self, block_and_node):
        block = block_and_node[0]
        node = block_and_node[1]
        try:
            # TODO: check if block is orphaned?
            height = node.getblock(block)["height"]
            reward = get_block_reward_sats(height)
            self.log.info(
                "Splitting %s sat block reward at height %s reward up for node: %s",
                reward,
                height,
                node.index,
            )
            wallet = ensure_miner(node)
            addresses = {}
            for _ in range(math.floor(reward / 10000000) - 1):
                addresses[wallet.getnewaddress(address_type="bech32m")] = "0.1"
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
                self.generate_block(node, node)
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
                # await asyncio.sleep(10)
                await asyncio.sleep(1 / int(self.options.txproductionrate))

    def send_transaction(self):
        try:
            # trunk-ignore(bandit/B311)
            from_node = random.choice(self.nodes)
            # trunk-ignore(bandit/B311)
            to_node = random.choice(self.nodes)
            wallet = ensure_miner(from_node)
            utxos = wallet.listunspent(include_unsafe=False, query_options={"maximumAmount": 0.1})
            if len(utxos) == 0:
                return
            fee_rate = Decimal("0.00001000")
            try:
                multiplier = Decimal(math.exp(random.random() * 0.2 - 0.1))
                fee_rate = from_node.estimatesmartfee(5)["feerate"] * multiplier
                fee_rate = fee_rate.quantize(Decimal(".00000001"))

            # trunk-ignore(bandit/B110)
            except Exception:
                pass
            # 1 in 1 out taproot transaction should be 111 vbytes
            fee = fee_rate * Decimal("0.111")
            amount = Decimal(utxos[0]["amount"])
            amount = amount - fee
            amount = amount.quantize(Decimal(".00000001"))

            raw_transaction_inputs = [
                {
                    "txid": utxos[0]["txid"],
                    "vout": utxos[0]["vout"],
                },
            ]
            raw_transaction_outputs = [
                {
                    to_node.getnewaddress(address_type="bech32m"): amount,
                },
            ]
            if amount < Decimal(MIN_UTXO_AMOUNT):
                raw_transaction_outputs = [
                    {
                        "data": "",
                    },
                ]
            tx = from_node.createrawtransaction(
                inputs=raw_transaction_inputs, outputs=raw_transaction_outputs
            )
            tx = from_node.signrawtransactionwithwallet(tx)["hex"]
            from_node.sendrawtransaction(tx)
            # runs in thread pool so mutex is needed
            with self.mutex:
                self.sent_txs += 1
                seconds_since_log = (datetime.now() - self.time_of_last_log).total_seconds()
                if seconds_since_log > 59:
                    self.log.info(
                        f"Sent roughly {'%.2f' % (self.sent_txs / 60)} transactions per second over the last minute"
                    )
                    self.log.info(
                        f"Roughly {'%.2f' % (self.failed_txs / 60)} transactions per second have failed over the last minute"
                    )
                    self.sent_txs = 0
                    self.failed_txs = 0
                    self.time_of_last_log = datetime.now()
        except Exception as e:
            with self.mutex:
                self.failed_txs += 1
            self.log.error("Error sending transaction: %s", e)


# bcli -rpcwallet=test-wallet -named send outputs="{\"$ADDRESS\": 1}" fee_rate=10

if __name__ == "__main__":
    print("Running Double TX Relay Scenario")
    DoubleTXRelay().main()
