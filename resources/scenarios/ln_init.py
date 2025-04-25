#!/usr/bin/env python3

import threading
from time import sleep

from commander import Commander
from ln_framework.ln import Policy


class LNInit(Commander):
    def set_test_params(self):
        self.num_nodes = None

    def add_options(self, parser):
        parser.description = "Fund LN wallets and open channels"
        parser.usage = "warnet run /path/to/ln_init.py"

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
        miner = self.ensure_miner(self.nodes[0])
        miner_addr = miner.getnewaddress()

        def gen(n):
            return self.generatetoaddress(self.nodes[0], n, miner_addr, sync_fun=self.no_op)

        self.log.info("Locking out of IBD...")
        gen(1)

        ##
        # WALLET ADDRESSES
        ##
        self.log.info("Getting LN wallet addresses...")
        ln_addrs = []

        def get_ln_addr(self, ln):
            success, address = ln.newaddress()
            if success:
                ln_addrs.append(address)
                self.log.info(f"Got wallet address {address} from {ln.name}")
            else:
                self.log.info(f"Couldn't get wallet address from {ln.name}")

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
        # 298 block base for miner wallet
        gen(297)
        # divvy up the goods, except fee.
        # 10 UTXOs per node means 10 channel opens per node per block
        split = (miner.getbalance() - 1) // len(ln_addrs) // 10
        sends = {}
        for _ in range(10):
            for addr in ln_addrs:
                sends[addr] = split
            miner.sendmany("", sends)
        # confirm funds in block 299
        gen(1)

        self.log.info(
            f"Waiting for funds to be spendable: 10x{split} BTC UTXOs each for {len(ln_addrs)} LN nodes"
        )

        def confirm_ln_balance(self, ln):
            bal = 0
            while True:
                bal = ln.walletbalance()
                if bal >= (split * 100000000):
                    self.log.info(f"LN node {ln.name} confirmed funds")
                    break
                sleep(1)

        fund_threads = [
            threading.Thread(target=confirm_ln_balance, args=(self, ln)) for ln in self.lns.values()
        ]
        for thread in fund_threads:
            thread.start()

        all(thread.join() is None for thread in fund_threads)
        self.log.info("All LN nodes are funded")

        ##
        # URIs
        ##
        self.log.info("Getting URIs for all LN nodes...")
        ln_uris = {}

        def get_ln_uri(self, ln):
            uri = None
            while True:
                uri = ln.uri()
                if uri:
                    ln_uris[ln.name] = uri
                    self.log.info(f"LN node {ln.name} has URI {uri}")
                    break
                sleep(1)

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
                        sleep(1)
                    else:
                        self.log.error(
                            f"Unexpected response attempting to connect {pair[0].name} -> {pair[1].name}:\n  {res}\n  ABORTING"
                        )
                        raise Exception(
                            f"Unable to connect {pair[0].name} -> {pair[1].name}:\n  {res}"
                        )

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
                self.log.info(
                    f"Sending channel open from {ch['source']} -> {ch['target']} with fee_rate={fee_rate}"
                )
                res = src.channel(
                    pk=tgt_pk,
                    capacity=ch["capacity"],
                    push_amt=ch["push_amt"],
                    fee_rate=fee_rate,
                )
                if res and "txid" in res:
                    ch["txid"] = res["txid"]
                    self.log.info(
                        f"Channel open {ch['source']} -> {ch['target']}\n  "
                        + f"outpoint={res['outpoint']}\n  "
                        + f"expected channel id: {ch['id']}"
                    )
                else:
                    ch["txid"] = "N/A"
                    self.log.info(
                        "Unexpected channel open response:\n  "
                        + f"From {ch['source']} -> {ch['target']} fee_rate={fee_rate}\n  "
                        + f"{res}"
                    )

            channels = sorted(ch_by_block[target_block], key=lambda ch: ch["id"]["index"])
            index = 0
            fee_rate = 5006  # s/vB, decreases by 5 per tx for up to 1000 txs per block
            ch_threads = []
            for ch in channels:
                index += 1  # noqa
                fee_rate -= 5
                assert index == ch["id"]["index"], "Channel ID indexes are not consecutive"
                assert fee_rate >= 1, "Too many TXs in block, out of fee range"
                t = threading.Thread(target=open_channel, args=(self, ch, fee_rate))
                sleep(0.25)
                t.start()
                ch_threads.append(t)

            all(thread.join() is None for thread in ch_threads)
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
            attempts = 0
            actual = 0
            while actual != expected:
                actual = len(ln.graph()["edges"])
                if attempts > 10:
                    break
                attempts += 1
                sleep(5)
            if actual == expected:
                self.log.info(f"LN {ln.name} has graph with all {expected} channels")
            else:
                self.log.error(
                    f"LN {ln.name} graph is INCOMPLETE - {actual} of {expected} channels"
                )

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
            res = ln.update(txid_hex, policy, capacity)
            assert len(res["failed_updates"]) == 0, (
                f" Failed updates: {res['failed_updates']}\n txid: {txid_hex}\n policy:{policy}"
            )

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
                actual = ln.graph()["edges"]
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
