#!/usr/bin/env python3
import time
from decimal import Decimal

from test_framework.authproxy import JSONRPCException
from test_framework.blocktools import COINBASE_MATURITY
from test_framework.wallet import MiniWallet
from warnet.test_framework_bridge import WarnetTestFramework

BLOCKS_WAIT_TILL_SPENDABLE = 101
MIN_UTXO_AMOUNT = Decimal(0.001)
AVERAGE_BLOCK_TIME = 600


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
            type=int,
            help="Rate per second at which transactions are generated. (default 5 tx/s)",
        )

    def generate_spendable_coins(self):
        num_blocks = COINBASE_MATURITY + 100
        self.log.info(f"Generating {num_blocks} blocks...")
        self.generate(self.miniwallet, num_blocks)
        self.log.info("Rescanning utxos")
        self.miniwallet.rescan_utxos()

    def split_utxos(self, num_outputs=1000) -> list:
        confirmed_utxos = self.miniwallet.get_utxos(confirmed_only=True)
        self.log.info(f"Got {len(confirmed_utxos)} confirmed utxos")
        self.log.info(f"Splitting each utxo into {num_outputs} utxos...")
        for i, utxo in enumerate(confirmed_utxos):
            tx = self.miniwallet.send_self_transfer_multi(
                from_node=self.nodes[0], utxos_to_spend=[utxo], num_outputs=num_outputs
            )
            self.log.info(f"Sent tx {i} of {len(confirmed_utxos)}: {tx['txid']}")
        self.generate(self.miniwallet, 3)
        self.miniwallet.rescan_utxos()
        self.log.info("Split complete")
        confirmed_utxos = self.miniwallet.get_utxos(confirmed_only=True)
        self.log.info(f"Got {len(confirmed_utxos)} confirmed utxos")
        return confirmed_utxos

    def produce_transactions(self, confirmed_utxos: list):
        self.log.info(
            f"Starting process to send anyone-can-spend transactions. Aiming for a rate of {self.options.txproductionrate} tx/s"
        )
        tx_count = 0
        target_interval = 1 / self.options.txproductionrate
        time_to_next_tx = 0

        start_time = time.time()
        interval_start_time = time.time()
        interval_end_time = time.time()
        next_log_time = start_time + 10

        while True:
            for node in self.nodes:
                time.sleep(time_to_next_tx)
                tx_start_time = time.time()

                if not confirmed_utxos:
                    self.generate(self.miniwallet, 1)
                    self.miniwallet.rescan_utxos()
                    confirmed_utxos = self.miniwallet.get_utxos(confirmed_only=True)

                utxo = confirmed_utxos.pop()
                try:
                    self.miniwallet.send_self_transfer(from_node=node, utxo_to_spend=utxo)
                    tx_count += 1
                except JSONRPCException as e:
                    self.log.warning(f"tx failed: {e}, continuing")

                # Adjust sleep before next send
                tx_end_time = time.time()
                tx_duration = tx_end_time - tx_start_time
                time_to_next_tx = max(0, target_interval - tx_duration)

                current_time = time.time()

                if current_time >= next_log_time:
                    interval_end_time = time.time()
                    tps = tx_count / (interval_end_time - interval_start_time)
                    self.log.info(f"Transactions per second (TPS): {tps}")
                    next_log_time += 10
                    interval_start_time = time.time()
                    tx_count = 0

    def run_test(self):
        self.log.info("Starting Double TX Relay Scenario")
        self.miniwallet = MiniWallet(self.nodes[0])
        self.generate_spendable_coins()
        confirmed_utxos = self.split_utxos(num_outputs=1000)
        self.produce_transactions(confirmed_utxos)


if __name__ == "__main__":
    print("Running Double TX Relay Scenario")
    DoubleTXRelay().main()

