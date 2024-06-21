#!/usr/bin/env python3
#
# Original: https://github.com/instagibbs/anticycle/blob/b5db30ec887ab0bc666bf0a94ff5b1fc17404ba8/anticycle.py#L1    # noqa

from decimal import Decimal
from collections import defaultdict
import struct
import zmq

from test_framework.test_node import TestNode
from warnet.test_framework_bridge import WarnetTestFramework

num_MB = 40

# How many times a utxo has to go from Top->Bottom to
# have its spending tx cached(if otherwise empty)
# Increasing this value reduces false positive rates
# and reduces memory usage accordingly.
CYCLE_THRESH = 1


def cli_help():
    return "Run an anti-cycling defense - based on instagibbs' work"


def run_anticycle(node: TestNode, logging):
    """
    Best effort mempool syncing to detect replacement cycling attacks
    """

    logging.info(" - anticycle - Starting anticycle")

    context = zmq.Context()

    # Create a socket of type SUBSCRIBE
    zmq_socket = context.socket(zmq.SUB)

    # Connect to the publisher's socket
    zmq_port = "28334"
    zmq_socket.connect(f"tcp://warnet-tank-000000-service:{zmq_port}")

    # Subscribe to all messages
    # You can specify a prefix filter here to receive specific messages
    zmq_socket.setsockopt_string(zmq.SUBSCRIBE, '')

    logging.info(f" - anticycle - Listening for messages on port {zmq_port}...")

    # txid -> serialized_tx
    # Cache for full transactions of which we believe are being replacement cycled.
    cycled_tx_cache = {}
    cycled_tx_cache_size = 0

    # utxo
    # The complete set of inputs that are spent by protected transactions.
    # This ensures that every cached tx in `cycled_tx_cache` can be independently spent, costing the
    # attacker a full "top block" slot each on inclusion.
    cycled_input_set = set([])

    # txid -> serialize_tx
    # This cache is for everything above "top block" that we hear about. This cache is required only
    # because the R (Remove) notification stream doesn't give full transactions. We need them to
    # compute top->bottom utxo changes.
    dummy_cache = {}
    dummy_cache_size = 0

    # utxo -> int
    # How many times in this epoch has the specific utxo gone from next block to non-next block?
    utxo_cycled_count = defaultdict(int)

    # utxo -> txid
    # Assign txids of protected transactions to utxos that appear to be replacement cycled. The full
    # tx is fetched from cycled_tx_cache.
    utxo_cache = {}

    # Simple anti-DoS max
    tx_cache_max_byte_size = num_MB * 1_000 * 1_000

    # These are populated by "R" events and cleared in subsequent "A" events. These are to track
    # top->bottom transitions
    # utxo -> removed tx's txid
    utxos_being_doublespent = {}

    logging.info("Getting Top Block fee")

    # If we can't estimate blocks in a scenario, we just assume anything we see can be mined.
    # Fix this post-cluster mempool with "next block"
    # chunk feerate checks.
    minrate: float = 0.000_010_00

    # "Top block" is considered next three blocks
    try:
        topblock_rate_btc_kvb = node.estimatesmartfee(3)["feerate"]
    except KeyError:
        topblock_rate_btc_kvb = minrate

    try:
        while True:
            # Receive a message
            topic, body, sequence = zmq_socket.recv_multipart()
            received_seq = struct.unpack('<I', sequence)[-1]
            txid = body[:32].hex()
            label = chr(body[32])

            if received_seq % 100 == 0:
                logging.info(
                    f" - anticycle - Transactions cached: {len(cycled_tx_cache)}, bytes cached: "
                    f"{cycled_tx_cache_size / 1000000}/{num_MB}MB, "
                    f"topblock rate: {topblock_rate_btc_kvb}")
                logging.info(f" - anticycle - Dummy cache: {len(dummy_cache)}, "
                             f"{dummy_cache_size / 1000000}/{num_MB}MB")

            if label == "A":
                logging.info(f" - anticycle - Tx {txid} added")
                entry = node.getmempoolentry(txid)
                if entry is None:
                    logging.info(f" - anticycle - {txid} mempool entry not found in when fetched")
                    utxos_being_doublespent.clear()
                    continue
                # We are allowing "packages" of ancestors.
                # What we really want is the mempool entry's chunk feerate.
                # And we actually don't want to track in-mempool utxos, only confirmed.
                tx_rate_btc_kvb = Decimal(entry['fees']['ancestor']) / entry['ancestorsize'] * 1000
                new_top_block = tx_rate_btc_kvb >= topblock_rate_btc_kvb
                if new_top_block:
                    logging.info(f" - anticycle - Transaction top block {txid}")
                    raw_tx = node.getrawtransaction(txid, True)
                    # Might have already been evicted/mined/etc
                    if raw_tx is None:
                        logging.info(f" - anticycle - {txid} not found in mempool when fetched")
                        utxos_being_doublespent.clear()
                        continue

                    logging.info(f" - anticycle - Transaction dummy cached {txid}")
                    # Cache tx to make sure we see it when it's being removed later
                    # FIXME get a better notification stream
                    dummy_cache[txid] = raw_tx
                    dummy_cache_size += len(raw_tx["hex"]) / 2

                    add_tx_prevouts = [(tx_input['txid'], tx_input['vout'])
                                       for tx_input in raw_tx["vin"]]
                    logging.info(f" - anticycle - prevouts being spent by new tx: "
                                 f"{add_tx_prevouts}")
                    logging.info(f" - anticycle - prevouts from removed transactions: "
                                 f"{utxos_being_doublespent}")

                    for prevout in add_tx_prevouts:
                        if prevout not in utxos_being_doublespent:
                            logging.info(f" - anticycle - {prevout} went from unspent to spent")
                            # Bottom->Top, clear cached transaction if any
                            if prevout in utxo_cache:
                                logging.info(f" - anticycle - Deleting cache entry for "
                                             f"{(tx_input['txid'], tx_input['vout'])}")
                                cycled_tx_cache_size -= len(cycled_tx_cache[utxo_cache[prevout]])
                                del cycled_tx_cache[utxo_cache[prevout]]
                                del utxo_cache[prevout]
                        else:
                            logging.info(f" - anticycle - {prevout} went from spent to spent")
                            # Top->Top, cache if entry is empty
                            if (prevout not in utxo_cache
                                    and utxo_cycled_count[prevout] >= CYCLE_THRESH):
                                # Get replaced txid and full tx from dummy_cache
                                removed_txid = utxos_being_doublespent[prevout]
                                removed_tx = dummy_cache[removed_txid]
                                removed_prevouts = [(tx_input['txid'], tx_input['vout'])
                                                    for tx_input in raw_tx["vin"]]
                                can_cache = all(prevout not in cycled_input_set
                                                for prevout in removed_prevouts)
                                if can_cache:
                                    logging.info(f" - anticycle - {prevout} has been RBF'd, "
                                                 f"caching {removed_txid}")
                                    utxo_cache[prevout] = removed_txid
                                    cycled_tx_cache[removed_txid] = removed_tx
                                    hex_len = len(cycled_tx_cache[utxo_cache[prevout]]["hex"]) / 2
                                    cycled_tx_cache_size += hex_len
                                    for removed_prevout in removed_prevouts:
                                        cycled_input_set.add(removed_prevout)
                                else:
                                    logging.info(f"{removed_txid} is not being cached due to "
                                                 f"conflicts in input cache")
                            # delete to detect remaining Top->Bottom later
                            del utxos_being_doublespent[prevout]

                    # Handle Top->Bottom: There are top block spends now unspent!
                    if len(utxos_being_doublespent) > 0:
                        logging.info(f" - anticycle - {len(utxos_being_doublespent)} "
                                     f"utxos going spent to unspent")
                        # things were double-spent and not removed with top block
                        for unspent_prevout, _ in utxos_being_doublespent.items():
                            # Count it first
                            utxo_cycled_count[unspent_prevout] += 1
                            logging.info(
                                f" - anticycle - {unspent_prevout} has been cycled "
                                f"{utxo_cycled_count[unspent_prevout]} times")

                            # If we have something cached, it might be free to re-enter now
                            if (unspent_prevout in utxo_cache
                                    and utxo_cache[unspent_prevout] in cycled_tx_cache):
                                raw_tx = cycled_tx_cache[utxo_cache[unspent_prevout]]["hex"]
                                send_ret = node.sendrawtransaction(raw_tx)
                                if send_ret:
                                    logging.info(f" - anticycle - Successfully resubmitted "
                                                 f"{send_ret}")
                                    logging.info(f" - anticycle - rawhex: {raw_tx}")

                # We processed the double-spends, clear
                utxos_being_doublespent.clear()

            elif label == "R":
                logging.info(f" - anticycle - Tx {txid} removed")
                # This tx is removed, perhaps replaced, next "A" message should be the tx replacing
                # it (conflict_tx)

                # If this tx is in the tx_cache, that implies it was top block we need to see which
                # utxos being non-top block once we see the next "A"
                # N.B. I am not sure at all the next "A" is actually a double-spend, that should be
                # checked!
                # I'm going off of functional tests.
                if txid in dummy_cache:
                    for tx_input in dummy_cache[txid]["vin"]:
                        utxos_being_doublespent[(tx_input["txid"], tx_input["vout"])] = txid

            elif label == "C" or label == "D":
                # logging.info(f"Block tip changed")
                # FIXME do something smarter, for now we just hope this isn't hit on short
                #  timeframes
                # Defender will have to resubmit enough again to be protected for the new period
                if (cycled_tx_cache_size > tx_cache_max_byte_size
                        or dummy_cache_size >= tx_cache_max_byte_size):
                    logging.info(f"wiping state")
                    dummy_cache.clear()
                    dummy_cache_size = 0
                    utxo_cache.clear()
                    utxo_cycled_count.clear()
                    utxos_being_doublespent.clear()
                    cycled_tx_cache.clear()
                    cycled_tx_cache_size = 0
                try:
                    topblock_rate_btc_kvb = node.estimatesmartfee(3)["feerate"]
                except KeyError:
                    topblock_rate_btc_kvb = minrate
    except KeyboardInterrupt:
        logging.info(" - anticycle - Program interrupted by user")
    finally:
        # Clean up on exit
        zmq_socket.close()
        context.term()


class AnticycleTest(WarnetTestFramework):

    def set_test_params(self):
        self.num_nodes = 2

    def run_test(self):
        run_anticycle(self.nodes[0],  self.log)


if __name__ == '__main__':
    AnticycleTest().main()
