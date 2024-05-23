# Original: https://github.com/instagibbs/anticycle/blob/f0f8c6a9b3d41c887e02610ef360589d05c4ebb9/anticycle.py#L1
import queue
from decimal import Decimal
from collections import defaultdict
import json
import logging
import os
import requests
from requests.auth import HTTPBasicAuth
import struct
import sys
import zmq

from scenarios.utils import get_service_ip
from test_framework.test_node import TestNode
from warnet.test_framework_bridge import WarnetTestFramework

from test_framework.authproxy import JSONRPCException

num_MB = 40

# # Configure logging settings
# logging.basicConfig(
#     stream=sys.stdout,
#     level=logging.INFO,
#     format='%(asctime)s - %(message)s',
#     datefmt='%Y-%m-%d %H:%M:%S'
# )

# Replace with cluster mempool threshholds
fee_url = 'https://mempool.space/api/v1/fees/recommended'

# How many times a utxo has to go from Top->Bottom to be
# have its spending tx cached(if otherwise empty)
# Increasing this value reducs false positive rates
# and reduces memory usage accordingly.
CYCLE_THRESH = 1


def cli_help():
    return "Run an anti-cycling defense"

def run_anticycle(node: TestNode, channel: None | queue.Queue, logging):
    '''
    Best effort mempool syncing to detect replacement cycling attacks
    '''

    logging.info(" -anticycle - Starting anticycle")
    node.log.info(" -anticycle - logging from node")
    
    context = zmq.Context()

    # Create a socket of type SUBSCRIBE
    socket = context.socket(zmq.SUB)

    # Connect to the publisher's socket
    external, internal = get_service_ip("warnet-tank-000000-service")
    port = "18332"  # specify the port you want to listen on
    socket.connect(f"tcp://{external}:{port}")

    # Subscribe to all messages
    # You can specify a prefix filter here to receive specific messages
    socket.setsockopt_string(zmq.SUBSCRIBE, '')

    logging.info(f" -anticycle - Listening for messages on {external}:{port}...")

    # txid -> tx cache (FIXME do better than this)
    # We store these anytime above top block
    # when real implementation would have access
    # to these when being evicted from the mempool
    # so we would only have to store in utxo_cache instead
    tx_cache = {}

    # Track total serialized size in bytesof the things we are caching
    # and use this as trigger for flushing.
    tx_cache_byte_size = 0

    # Note the attacker can simply be incrementally RBFing through that much
    # size after paying once for "top block".
    # Having just in time access to something being evicted is what
    # we really want but for now we'll just roughly count what we're storing.
    # FIXME if we're going with this wiping window, maybe make it less
    # deterministic to avoid completely predictable windows. Does this matter?
    tx_cache_max_byte_size = num_MB * 1000 * 1000

    # utxo -> protected-txid cache
    # this would the real bottleneck in terms of space if we had access to the
    # transactions being evicted. We don't so for now full tx are in tx_cache
    utxo_cache = {}

    # utxo -> count of topblock->nontopblock transitions
    utxo_unspent_count = defaultdict(int)

    # These are populated by "R" events and cleared in
    # subsequent "A" events. These are to track
    # top->nontop transitions
    # utxo -> removed tx's txid
    utxos_being_doublespent = {}

    logging.info("anticycle - Getting Top Block fee")
    topblock_rate_sat_vb = requests.get(fee_url).json()["fastestFee"]
    topblock_rate_btc_kvb = Decimal(topblock_rate_sat_vb) * 1000 / 100000000
    logging.info(f"anticycle - topblock rate: {topblock_rate_btc_kvb}")

    try:
        while True:
            item = channel and channel.get()
            if item == "shutdown":
                logging.info("anticycle - Anticycle got shutdown message.")
                break

            # Receive a message
            topic, body, sequence = socket.recv_multipart()
            received_seq = struct.unpack('<I', sequence)[-1]
            txid = body[:32].hex()
            label = chr(body[32])

            if received_seq % 100 == 0:
                logging.info(f"anticycle - Transactions cached: {len(tx_cache)}, "
                             f"bytes cached: {tx_cache_byte_size / 1000000}/{num_MB}MB, "
                             f"topblock rate: {topblock_rate_sat_vb}")

            if label == "A":
                logging.info(f"anticycle - Tx {txid} added")
                try:
                    entry = node.getmempoolentry(txid)
                except JSONRPCException:
                    entry = None
                if entry is not None:
                    if entry['ancestorcount'] != 1:
                        # Only supporting singletons for now ala HTLC-X transactions
                        # Can extend to 1P1C pretty easily.
                        continue
                    tx_rate_btc_kvb = Decimal(entry['fees']['ancestor']) / entry['ancestorsize'] * 1000
                    new_top_block = tx_rate_btc_kvb >= topblock_rate_btc_kvb
                    if new_top_block:
                        raw_tx = node.getrawtransaction(txid)
                        # We need to cache if it's removed later, since by the time
                        # we are told it's removed, it's already gone. Would be nice
                        # to get it when it's removed, or persist to disk, or whatever.
                        tx_cache[txid] = raw_tx
                        tx_cache_byte_size += int(len(raw_tx["hex"]) / 2)

                        for tx_input in raw_tx["vin"]:
                            prevout = (tx_input['txid'], tx_input['vout'])
                            if prevout not in utxos_being_doublespent and prevout in utxo_cache:
                                # Bottom->Top, clear cached transaction
                                logging.info(f"anticycle - Deleting cache entry for {(tx_input['txid'], tx_input['vout'])}")
                                del utxo_cache[prevout]
                            elif prevout in utxos_being_doublespent and prevout not in utxo_cache:
                                if utxo_unspent_count[prevout] >= CYCLE_THRESH:
                                    logging.info(f"anticycle - {prevout} has been RBF'd, caching {removed_txid}")
                                    # Top->Top, cache the removed transaction
                                    utxo_cache[prevout] = utxos_being_doublespent[prevout]
                                    del utxos_being_doublespent[prevout]  # delete to detect Top->Bottom later

                    # Handle Top->Bottom: top utxos gone unspent
                    if len(utxos_being_doublespent) > 0:
                        # things were double-spent and not removed with top block
                        for prevout, removed_txid in utxos_being_doublespent.items():
                            if removed_txid in tx_cache:
                                utxo_unspent_count[prevout] += 1

                                if utxo_unspent_count[prevout] >= CYCLE_THRESH:
                                    logging.info(
                                        f"anticycle - {prevout} has been cycled {utxo_unspent_count[prevout]} times, maybe caching {removed_txid}")
                                    # cache removed tx if nothing cached for this utxo
                                    if prevout not in utxo_cache:
                                        logging.info(f"anticycle - cached {removed_txid}")
                                        utxo_cache[prevout] = removed_txid

                                # resubmit cached utxo tx
                                raw_tx = tx_cache[utxo_cache[prevout]]["hex"]
                                send_ret = node.sendrawtransaction(raw_tx)
                                if send_ret:
                                    logging.info(f"anticycle - Successfully resubmitted {send_ret}")
                                    logging.info(f"anticycle - rawhex: {raw_tx}")

                # We processed the double-spends, clear
                utxos_being_doublespent.clear()
            elif label == "R":
                logging.info(f"anticycle - Tx {txid} removed")
                # This tx is removed, perhaps replaced, next "A" message should be the tx replacing it(conflict_tx)

                # If this tx is in the tx_cache, that implies it was top block
                # we need to see which utxos being non-top block once we see
                # the next "A"
                # N.B. I am not sure at all the next "A" is actually a double-spend, that should be checked!
                # I'm going off of functional tests.
                if txid in tx_cache:
                    for tx_input in tx_cache[txid]["vin"]:
                        utxos_being_doublespent[(tx_input["txid"], tx_input["vout"])] = txid

            elif label == "C" or label == "D":
                #logging.info(f"anticycle - Block tip changed")
                # FIXME do something smarter, for now we just hope this isn't hit on short timeframes
                # Defender will have to resubmit enough again to be protected for the new period
                if tx_cache_byte_size > tx_cache_max_byte_size:
                    logging.info(f"anticycle -wiping state")
                    utxo_cache.clear()
                    utxo_unspent_count.clear()
                    utxos_being_doublespent.clear()
                    tx_cache.clear()
                    tx_cache_byte_size = 0
                topblock_rate_sat_vb = requests.get(fee_url).json()["fastestFee"]
                topblock_rate_btc_kvb = Decimal(topblock_rate_sat_vb) * 1000 / 100000000
    except KeyboardInterrupt:
        logging.info("anticycle - Program interrupted by user")
    finally:
        # Clean up on exit
        socket.close()
        context.term()


class ReplacementCyclingTest(WarnetTestFramework):

    def set_test_params(self):
        self.num_nodes = 2

    def run_test(self):
        run_anticycle(self.nodes[0], None, self.log)


if __name__ == '__main__':
    ReplacementCyclingTest().main()