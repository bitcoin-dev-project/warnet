#!/usr/bin/env python3

import threading
from time import sleep

from commander import Commander
from ln_framework.ln import (
    CHANNEL_OPEN_START_HEIGHT,
    CHANNEL_OPENS_PER_BLOCK,
    FEE_RATE_DECREMENT,
    MAX_FEE_RATE,
    Policy,
)
from test_framework.address import address_to_scriptpubkey
from test_framework.messages import (
    COIN,
    CTransaction,
    CTxOut,
)


class LNInit(Commander):
    def set_test_params(self):
        self.num_nodes = None

    def add_options(self, parser):
        parser.description = "Fund LN wallets and open channels"
        parser.usage = "warnet run /path/to/ln_init.py"
        parser.add_argument(
            "--miner",
            dest="miner",
            type=str,
            help="Select one tank by name as the blockchain miner",
        )

    def run_test(self):
        ##
        # L1 P2P
        ##
        self.log.info("Waiting for L1 p2p network connections...")
        self.wait_for_tanks_connected()

        ##
        # MINER
        ##
        self.log.info("Setting up miner...")
        if self.options.miner:
            self.log.info(f"Parsed 'miner' argument: {self.options.miner}")
            mining_tank = self.tanks[self.options.miner]
        elif "miner" in self.tanks:
            # or choose the tank with the right name
            self.log.info("Found tank named 'miner'")
            mining_tank = self.tanks["miner"]
        else:
            mining_tank = self.nodes[0]
            self.log.info(f"Using tank {mining_tank.tank} as miner")

        miner = self.ensure_miner(mining_tank)
        miner_addr = miner.getnewaddress()

        def gen(n):
            # Take all the time you need to generate those blocks
            mining_tank.rpc_timeout = 6000
            return self.generatetoaddress(mining_tank, n, miner_addr, sync_fun=self.no_op)

        self.log.info("Locking out of IBD...")
        gen(1)

        ##
        # WALLET ADDRESSES
        ##
        self.log.info("Getting LN wallet addresses...")
        ln_addrs = {}

        def get_ln_addr(self, ln):
            while True:
                try:
                    address = ln.newaddress()
                    ln_addrs[ln.name] = address
                    self.log.info(f"Got wallet address {address} from {ln.name}")
                    break
                except Exception as e:
                    self.log.info(
                        f"Couldn't get wallet address from {ln.name} because {e}, retrying in 5 seconds..."
                    )
                    sleep(5)

        addr_threads = [
            threading.Thread(target=get_ln_addr, args=(self, ln)) for ln in self.lns.values()
        ]
        for thread in addr_threads:
            thread.start()

        all(thread.join() is None for thread in addr_threads)
        self.log.info(f"Got {len(ln_addrs)} addresses from {len(self.lns)} LN nodes")

        ##
        # FUNDS
        ##
        self.log.info("Funding LN wallets...")
        # One past block generated already to lock out IBD
        # One next block to consolidate the miner's coins
        # One next block to confirm the distributed coins
        # Then the channel open TXs go in the expected block height
        gen(CHANNEL_OPEN_START_HEIGHT - 4)
        # divvy up the goods, except fee.
        # Multiple UTXOs per LN wallet so multiple channels can be opened per block
        miner_balance = int(miner.getbalance())
        # To reduce individual TX weight, consolidate all outputs before distribution
        miner.sendtoaddress(miner_addr, miner_balance - 1)
        gen(1)
        helicopter = CTransaction()

        # Provide the source LN node for each channel with a UTXO just big enough
        # to open that channel with its capacity plus fee.
        channel_openers = []
        for ch in self.channels:
            if ch["source"] not in channel_openers:
                channel_openers.append(ch["source"])
            addr = ln_addrs[ch["source"]]
            # More than enough to open the channel plus fee and cover LND's "maxFeeRatio"
            # As long as all channel capacities are < 4 BTC the change output will be
            # larger and occupy tx output 1, leaving the actual channel open at output 0
            sat_amt = 10 * COIN
            helicopter.vout.append(CTxOut(sat_amt, address_to_scriptpubkey(addr)))
        rawtx = miner.fundrawtransaction(helicopter.serialize().hex())
        signed_tx = miner.signrawtransactionwithwallet(rawtx["hex"])["hex"]
        txid = miner.sendrawtransaction(signed_tx)
        # confirm funds in last block before channel opens
        gen(1)

        txstats = miner.gettransaction(txid)
        self.log.info(
            "Funds distribution from miner:\n  "
            + f"txid: {txid}\n  "
            + f"# outputs: {len(txstats['details'])}\n  "
            + f"total amount: {txstats['amount']}\n  "
            + f"remaining miner balance: {miner.getbalance()}"
        )

        self.log.info("Waiting for funds to be spendable by channel-openers")

        def confirm_ln_balance(self, ln_name):
            ln = self.lns[ln_name]
            while True:
                try:
                    bal = ln.walletbalance()
                    if bal >= 0:
                        self.log.info(f"LN node {ln_name} confirmed funds")
                        break
                    else:
                        self.log.info(f"Got 0 balance from {ln_name} retrying in 5 seconds...")
                        sleep(5)
                except Exception as e:
                    self.log.info(
                        f"Couldn't get balance from {ln_name} because {e}, retrying in 5 seconds..."
                    )
                    sleep(5)

        fund_threads = [
            threading.Thread(target=confirm_ln_balance, args=(self, ln_name))
            for ln_name in channel_openers
        ]
        for thread in fund_threads:
            thread.start()

        all(thread.join() is None for thread in fund_threads)
        self.log.info("All channel-opening LN nodes are funded")

        ##
        # URIs
        ##
        self.log.info("Getting URIs for all LN nodes...")
        ln_uris = {}

        def get_ln_uri(self, ln):
            while True:
                try:
                    uri = ln.uri()
                    ln_uris[ln.name] = uri
                    self.log.info(f"LN node {ln.name} has URI {uri}")
                    break
                except Exception as e:
                    self.log.info(
                        f"Couldn't get URI from {ln.name} because {e}, retrying in 5 seconds..."
                    )
                    sleep(5)

        uri_threads = [
            threading.Thread(target=get_ln_uri, args=(self, ln)) for ln in self.lns.values()
        ]
        for thread in uri_threads:
            thread.start()

        all(thread.join() is None for thread in uri_threads)
        self.log.info("Got URIs from all LN nodes")

        ##
        # P2P CONNECTIONS
        ##
        self.log.info("Adding p2p connections to LN nodes...")
        # (source: LND, target_uri: str) tuples of LND instances
        connections = []
        # Cycle graph through all LN nodes
        nodes = list(self.lns.values())
        prev_node = nodes[-1]
        for node in nodes:
            connections.append((node, prev_node))
            prev_node = node
        # Explicit connections between every pair of channel partners
        for ch in self.channels:
            src = self.lns[ch["source"]]
            tgt = self.lns[ch["target"]]
            # Avoid duplicates and reciprocals
            if (src, tgt) not in connections and (tgt, src) not in connections:
                connections.append((src, tgt))

        def connect_ln(self, pair):
            while True:
                try:
                    res = pair[0].connect(ln_uris[pair[1].name])
                    if res == {}:
                        self.log.info(f"Connected LN nodes {pair[0].name} -> {pair[1].name}")
                        break
                    if "message" in res:
                        if "already connected" in res["message"]:
                            self.log.info(
                                f"Already connected LN nodes {pair[0].name} -> {pair[1].name}"
                            )
                            break
                        if "process of starting" in res["message"]:
                            self.log.info(
                                f"{pair[0].name} not ready for connections yet, wait and retry..."
                            )
                            sleep(5)
                        else:
                            raise Exception(res)
                except Exception as e:
                    self.log.info(
                        f"Couldn't connect {pair[0].name} -> {pair[1].name} because {e}, retrying in 5 seconds..."
                    )
                    sleep(5)

        p2p_threads = [
            threading.Thread(target=connect_ln, args=(self, pair)) for pair in connections
        ]
        for thread in p2p_threads:
            sleep(0.25)
            thread.start()

        all(thread.join() is None for thread in p2p_threads)
        self.log.info("Established all LN p2p connections")

        ##
        # CHANNELS
        ##
        self.log.info("Opening lightning channels...")
        # Sort the channels by assigned block and index
        # so their channel ids are deterministic
        ch_by_block = {}
        for ch in self.channels:
            if "id" not in ch or "block" not in ch["id"]:
                raise Exception(f"LN Channel {ch} not found")
            block = ch["id"]["block"]
            if block not in ch_by_block:
                ch_by_block[block] = [ch]
            else:
                ch_by_block[block].append(ch)
        blocks = list(ch_by_block.keys())
        blocks = sorted(blocks)

        for target_block in blocks:
            # First make sure the target block is the next block
            current_height = self.nodes[0].getblockcount()
            need = target_block - current_height
            if need < 1:
                raise Exception("Blockchain too long for deterministic channel ID")
            if need > 1:
                gen(need - 1)

            def open_channel(self, ch, fee_rate):
                src = self.lns[ch["source"]]
                tgt_uri = ln_uris[ch["target"]]
                tgt_pk, _ = tgt_uri.split("@")
                log = f"  {ch['source']} -> {ch['target']}\n  {ch['id']} fee: {fee_rate}"
                while True:
                    self.log.info(f"Sending channel open:\n{log}")
                    try:
                        res = src.channel(
                            pk=tgt_pk,
                            capacity=ch["capacity"],
                            push_amt=ch["push_amt"],
                            fee_rate=fee_rate,
                        )
                        ch["txid"] = res["txid"]
                        ch["outpoint"] = res["outpoint"]
                        self.log.info(
                            f"Channel open success:\n{log}\n  outpoint: {res['outpoint']}"
                        )
                        break
                    except Exception as e:
                        self.log.info(
                            f"Couldn't open channel:\n{log}\n  {e}\n  Retrying in 5 seconds..."
                        )
                        sleep(5)

            channels = sorted(ch_by_block[target_block], key=lambda ch: ch["id"]["index"])
            if len(channels) > CHANNEL_OPENS_PER_BLOCK:
                raise Exception(
                    f"Too many channels in block {target_block}: {len(channels)} / Maximum: {CHANNEL_OPENS_PER_BLOCK}"
                )
            index = 0
            fee_rate = MAX_FEE_RATE
            ch_threads = []
            for ch in channels:
                index += 1  # noqa
                fee_rate -= FEE_RATE_DECREMENT
                assert index == ch["id"]["index"], "Channel ID indexes are not consecutive"
                assert fee_rate >= 1, "Too many TXs in block, out of fee range"
                t = threading.Thread(target=open_channel, args=(self, ch, fee_rate))
                sleep(0.25)
                t.start()
                ch_threads.append(t)

            all(thread.join() is None for thread in ch_threads)
            for ch in channels:
                if ch["outpoint"][-2:] != ":0":
                    self.log.error(f"Channel open outpoint not tx output index 0\n  {ch}")
                    raise Exception("Channel determinism ruined, abort!")

            self.log.info(f"Waiting for {len(channels)} channel opens in mempool...")
            self.wait_until(
                lambda channels=channels: self.nodes[0].getmempoolinfo()["size"] >= len(channels),
                timeout=500,
            )
            block_hash = gen(1)[0]
            self.log.info(f"Confirmed {len(channels)} channel opens in block {target_block}")
            self.log.info("Checking deterministic channel IDs in block...")
            block = self.nodes[0].getblock(block_hash)
            block_txs = block["tx"]
            block_height = block["height"]
            for ch in channels:
                assert ch["txid"] != "N/A", f"Channel:{ch} did not receive txid"
                assert ch["id"]["block"] == block_height, f"Actual block:{block_height}\n{ch}"
                assert block_txs[ch["id"]["index"]] == ch["txid"], (
                    f"Actual txid:{block_txs[ch['id']['index']]}\n{ch}"
                )
            self.log.info("👍")

        gen(5)
        self.log.info(f"Confirmed {len(self.channels)} total channel opens")

        self.log.info("Waiting for channel announcement gossip...")

        def ln_all_chs(self, ln):
            expected = len(self.channels)
            actual = 0
            while actual != expected:
                try:
                    actual = len(ln.graph()["edges"])
                    if actual == expected:
                        self.log.info(f"LN {ln.name} has graph with all {expected} channels")
                        break
                    else:
                        self.log.info(
                            f"LN {ln.name} graph is incomplete - {actual} of {expected} channels, checking again in 5 seconds..."
                        )
                        sleep(5)
                except Exception as e:
                    self.log.info(
                        f"Couldn't check graph from {ln.name} because {e}, retrying in 5 seconds..."
                    )
                    sleep(5)

        ch_ann_threads = [
            threading.Thread(target=ln_all_chs, args=(self, ln)) for ln in self.lns.values()
        ]
        for thread in ch_ann_threads:
            sleep(0.25)
            thread.start()

        all(thread.join() is None for thread in ch_ann_threads)
        self.log.info("All LN nodes have complete graph")

        ##
        # UPDATE CHANNEL POLICIES
        ##
        self.log.info("Updating channel policies...")

        def update_policy(self, ln, txid_hex, policy, capacity):
            self.log.info(f"Sending update from {ln.name} for channel with outpoint: {txid_hex}:0")
            res = None
            while res is None:
                try:
                    res = ln.update(txid_hex, policy, capacity)
                    if len(res["failed_updates"]) != 0:
                        self.log.info(
                            f" Failed updates: {res['failed_updates']}\n txid: {txid_hex}\n policy:{policy}\n retrying in 5 seconds..."
                        )
                        sleep(5)
                        continue
                    break
                except Exception as e:
                    self.log.info(
                        f"Couldn't update channel policy for {ln.name} because {e}, retrying in 5 seconds..."
                    )
                    sleep(5)

        update_threads = []
        for ch in self.channels:
            if "source_policy" in ch:
                ts = threading.Thread(
                    target=update_policy,
                    args=(
                        self,
                        self.lns[ch["source"]],
                        ch["txid"],
                        ch["source_policy"],
                        ch["capacity"],
                    ),
                )
                sleep(0.25)
                ts.start()
                update_threads.append(ts)
            if "target_policy" in ch:
                tt = threading.Thread(
                    target=update_policy,
                    args=(
                        self,
                        self.lns[ch["target"]],
                        ch["txid"],
                        ch["target_policy"],
                        ch["capacity"],
                    ),
                )
                sleep(0.25)
                tt.start()
                update_threads.append(tt)
        count = len(update_threads)

        all(thread.join() is None for thread in update_threads)
        self.log.info(f"Sent {count} channel policy updates")

        self.log.info("Waiting for all channel policy gossip to synchronize...")

        def policy_equal(pol1, pol2, capacity):
            return pol1.to_lnd_chanpolicy(capacity) == pol2.to_lnd_chanpolicy(capacity)

        def matching_graph(self, expected, ln):
            done = False
            while not done:
                try:
                    actual = ln.graph()["edges"]
                except Exception as e:
                    self.log.info(
                        f"Couldn't get graph from {ln.name} because {e}, retrying in 5 seconds..."
                    )
                    sleep(5)
                    continue

                self.log.debug(f"LN {ln.name} channel graph edges: {actual}")
                if len(actual) > 0:
                    done = True
                    assert len(expected) == len(actual), (
                        f"Expected edges {len(expected)}, actual edges {len(actual)}\n{actual}"
                    )
                for i, actual_ch in enumerate(actual):
                    expected_ch = expected[i]
                    capacity = expected_ch["capacity"]
                    # We assert this because it isn't updated as part of policy.
                    # If this fails we have a bigger issue
                    assert int(actual_ch["capacity"]) == capacity, (
                        f"LN {ln.name} graph capacity mismatch:\n actual: {actual_ch['capacity']}\n expected: {capacity}"
                    )

                    # Policies were not defined in network.yaml
                    if "source_policy" not in expected_ch or "target_policy" not in expected_ch:
                        continue

                    # policy actual/expected source/target
                    polas = Policy.from_lnd_describegraph(actual_ch["node1_policy"])
                    polat = Policy.from_lnd_describegraph(actual_ch["node2_policy"])
                    poles = Policy(**expected_ch["source_policy"])
                    polet = Policy(**expected_ch["target_policy"])
                    # Allow policy swap when comparing channels
                    if policy_equal(polas, poles, capacity) and policy_equal(
                        polat, polet, capacity
                    ):
                        continue
                    if policy_equal(polas, polet, capacity) and policy_equal(
                        polat, poles, capacity
                    ):
                        continue
                    done = False
                if done:
                    self.log.info(f"LN {ln.name} graph channel policies all match expected source")
                else:
                    sleep(5)

        expected = sorted(self.channels, key=lambda ch: (ch["id"]["block"], ch["id"]["index"]))
        policy_threads = [
            threading.Thread(target=matching_graph, args=(self, expected, ln))
            for ln in self.lns.values()
        ]
        for thread in policy_threads:
            sleep(0.25)
            thread.start()

        all(thread.join() is None for thread in policy_threads)
        self.log.info("All LN nodes have matching graph!")


def main():
    LNInit().main()


if __name__ == "__main__":
    main()
