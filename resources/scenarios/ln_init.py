#!/usr/bin/env python3

import threading
from collections import Counter, defaultdict
from decimal import Decimal
from time import sleep, time

from commander import Commander
from ln_framework.ln import (
    CHANNEL_FUNDING_BUFFER,
    CHANNEL_OPEN_FEE_RATE,
    CHANNEL_OPEN_START_HEIGHT,
    CHANNEL_OPENS_PER_BLOCK,
    FUNDING_OUTPUTS_PER_TX,
    FUNDING_TX_FEE,
    GOSSIP_STALL_TIMEOUT,
    LDK_ANCHOR_RESERVE,
    MAX_FUNDING_TXS,
    Policy,
)
from test_framework.address import address_to_scriptpubkey
from test_framework.messages import (
    COIN,
    COutPoint,
    CTransaction,
    CTxIn,
    CTxOut,
)


def plan_funding(channels, impls):
    """
    UTXOs to fund LN nodes with, just enough for the channels they open.
    Multiple UTXOs per LN wallet so multiple channels can be opened per block.
    Returns a list of (LN node name, amount in sats, channel the UTXO must fund or None)
    """
    funding = []  # (LN node name, amount in sats, channel the UTXO is for or None)
    opens = defaultdict(list)
    for ch in channels:
        opens[ch["source"]].append(ch)
    for name, chs in opens.items():
        impl = impls[name]
        if impl == "eclair":
            # Eclair opens its channels concurrently and its Bitcoin Core wallet
            # picks the coins, spending unconfirmed change if no confirmed coin is
            # big enough. Make each UTXO big enough for any of its channels.
            amount = max(ch["capacity"] for ch in chs) + CHANNEL_FUNDING_BUFFER
            funding += [(name, amount, None) for _ in chs]
            continue
        for ch in chs:
            # LND and CLN are told which UTXO funds each channel. LND sorts the
            # funding transaction outputs by amount, so the change must be larger
            # than the channel to put the channel at output 0. CLN always puts
            # the channel first. LDK opens one channel at a time and can spend
            # change from its previous opens.
            amount = (2 if impl == "lnd" else 1) * ch["capacity"] + CHANNEL_FUNDING_BUFFER
            funding.append((name, amount, ch if impl in ("lnd", "cln") else None))
    # LDK rejects inbound anchor channels unless it has an on-chain
    # reserve to fee-bump a force close.
    ldk_inbound = Counter(ch["target"] for ch in channels if impls[ch["target"]] == "ldk")
    for name, count in ldk_inbound.items():
        funding.append((name, LDK_ANCHOR_RESERVE * count + CHANNEL_FUNDING_BUFFER, None))
    return funding


def distribute_funds(miner, gen, ln_addrs, funding, log):
    """
    Send the UTXOs of plan_funding() from the miner's wallet to the LN wallets and
    confirm them in the next block. Records the UTXO of each channel that must be
    funded with a specific one as ch["funding_utxo"].
    """
    if not funding:
        return
    # Split the outputs over transactions below the standard weight limit. They
    # must all be confirmed in the block before the first channel opens.
    batches = [
        funding[first : first + FUNDING_OUTPUTS_PER_TX]
        for first in range(0, len(funding), FUNDING_OUTPUTS_PER_TX)
    ]
    if len(batches) > MAX_FUNDING_TXS:
        raise Exception(
            f"{len(funding)} funding outputs don't fit in one block, the maximum is "
            f"{MAX_FUNDING_TXS * FUNDING_OUTPUTS_PER_TX}. Use fewer channels."
        )
    total = sum(amount for _, amount, _ in funding)
    # Only coinbases with 100 confirmations are spendable
    miner_balance = int(miner.getbalance())
    nodes = len({name for name, _, _ in funding})
    log.info(
        f"Funding {nodes} LN nodes with {total / COIN:.8f} BTC in {len(funding)} UTXOs "
        f"from {len(batches)} transactions, miner has {miner_balance} BTC"
    )
    if total + len(batches) * FUNDING_TX_FEE > (miner_balance - 1) * COIN:
        raise Exception(
            f"The miner only has {miner_balance} BTC to fund {total / COIN:.8f} BTC "
            f"of channels. Use smaller or fewer channels."
        )
    # Consolidate the miner's coins into one coin per funding transaction, to
    # reduce their weight. They can't spend each other's unconfirmed change,
    # Bitcoin Core limits clusters of unconfirmed transactions to 101 kvB.
    batch_amounts = {}
    for batch in batches:
        amount = sum(amount for _, amount, _ in batch) + FUNDING_TX_FEE
        batch_amounts[miner.getnewaddress()] = Decimal(amount) / COIN
    consolidation_txid = miner.sendmany("", batch_amounts)
    gen(1)
    consolidation = miner.decoderawtransaction(miner.gettransaction(consolidation_txid)["hex"])
    # sendmany shuffles the outputs
    batch_vouts = {vout["scriptPubKey"].get("address"): vout["n"] for vout in consolidation["vout"]}

    for address, batch in zip(batch_amounts, batches):
        helicopter = CTransaction()
        prevout = COutPoint(int(consolidation_txid, 16), batch_vouts[address])
        helicopter.vin.append(CTxIn(prevout))
        for name, amount, _ in batch:
            helicopter.vout.append(CTxOut(amount, address_to_scriptpubkey(ln_addrs[name])))
        # Add the change after our outputs so their indexes don't change
        rawtx = miner.fundrawtransaction(
            helicopter.serialize().hex(),
            {"changePosition": len(batch), "add_inputs": False},
        )
        signed_tx = miner.signrawtransactionwithwallet(rawtx["hex"])["hex"]
        txid = miner.sendrawtransaction(signed_tx)
        for vout, (_, _, ch) in enumerate(batch):
            if ch is not None:
                ch["funding_utxo"] = f"{txid}:{vout}"
        log.info(f"Funding tx {txid} with {len(batch)} outputs")
    # confirm funds in last block before channel opens
    gen(1)
    log.info(f"Funds distributed, remaining miner balance: {miner.getbalance()}")


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
        # Exceptions in worker threads are only printed, collect them so
        # ln_init fails instead of reporting success.
        thread_errors = []

        def excepthook(args):
            thread_errors.append(args.exc_value)
            threading.__excepthook__(args)

        threading.excepthook = excepthook

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

        ##
        # Run only once per network, do this after p2p connections
        # so everyone is on the same chain if there is a restart
        # with inconsistent persistence.
        ##
        if mining_tank.getblockcount() > 0:
            self.log.info("Chain already exists, exiting")
            return

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
        funding = plan_funding(self.channels, {name: ln.impl for name, ln in self.lns.items()})
        channel_openers = list(dict.fromkeys(name for name, _, _ in funding))

        distribute_funds(miner, gen, ln_addrs, funding, self.log)

        self.log.info("Waiting for funds to be spendable by channel-openers")

        def confirm_ln_balance(self, ln_name):
            ln = self.lns[ln_name]
            while True:
                try:
                    bal = ln.walletbalance()
                    # LDK won't open or accept channels before its wallet sees the funds
                    if bal > 0 or ln.impl != "ldk":
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
                            utxo=ch.get("funding_utxo"),
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
                        # The peers may have been disconnected, e.g. by a restart. Peers
                        # don't reconnect to nodes they didn't dial themselves.
                        try:
                            src.connect(tgt_uri)
                        except Exception as e:
                            self.log.info(
                                f"Couldn't reconnect {ch['source']} -> {ch['target']}: {e}"
                            )

            channels = sorted(ch_by_block[target_block], key=lambda ch: ch["id"]["index"])
            if len(channels) > CHANNEL_OPENS_PER_BLOCK:
                raise Exception(
                    f"Too many channels in block {target_block}: {len(channels)} / Maximum: {CHANNEL_OPENS_PER_BLOCK}"
                )

            # LDK funds channels with unconfirmed change from its earlier opens, and
            # a child transaction can't be mined ahead of its parent. Open each LDK
            # node's channels one at a time in index order, so a parent always has
            # a lower index (higher rank below) than its children.
            def open_channels_in_order(self, chs, fee_rate):
                for ch in chs:
                    open_channel(self, ch, fee_rate)

            index = 0
            ldk_opens = {}
            ch_threads = []
            for ch in channels:
                index += 1  # noqa
                assert index == ch["id"]["index"], "Channel ID indexes are not consecutive"
                if self.lns[ch["source"]].impl == "ldk":
                    ldk_opens.setdefault(ch["source"], []).append(ch)
                    continue
                t = threading.Thread(target=open_channel, args=(self, ch, CHANNEL_OPEN_FEE_RATE))
                sleep(0.25)
                t.start()
                ch_threads.append(t)
            for chs in ldk_opens.values():
                t = threading.Thread(
                    target=open_channels_in_order, args=(self, chs, CHANNEL_OPEN_FEE_RATE)
                )
                t.start()
                ch_threads.append(t)

            all(thread.join() is None for thread in ch_threads)
            for ch in channels:
                if ch["outpoint"][-2:] != ":0":
                    if self.lns[ch["source"]].impl in ("eclair", "ldk"):
                        # Eclair funds channels from its Bitcoin Core wallet and
                        # LDK from its BDK wallet, both randomize the position
                        # of the change output.
                        self.log.warning(f"Channel open outpoint not tx output index 0\n  {ch}")
                        continue
                    self.log.error(f"Channel open outpoint not tx output index 0\n  {ch}")
                    raise Exception("Channel determinism ruined, abort!")

            self.log.info(f"Waiting for {len(channels)} channel opens in mempool...")
            self.wait_until(
                lambda channels=channels: (
                    {ch["txid"] for ch in channels} <= set(mining_tank.getrawmempool())
                ),
                timeout=500,
            )
            # Place the funding transactions in channel index order by making the
            # miner rank them at decreasing fee rates, regardless of what they
            # paid. Implementations don't all pay exactly the fee rate they are
            # asked for, e.g. CLN over-estimates the size of its transaction.
            for ch in channels:
                entry = mining_tank.getmempoolentry(ch["txid"])
                paid = round(entry["fees"]["base"] * COIN)
                rank_fee_rate = (len(channels) - ch["id"]["index"] + 1) * 1000
                delta = rank_fee_rate * entry["vsize"] - paid
                self.log.info(
                    f"Channel {ch['id']} paid {paid / entry['vsize']:.2f} s/vB, "
                    f"ranked at {rank_fee_rate} s/vB. Applying delta: {delta}"
                )
                mining_tank.prioritisetransaction(ch["txid"], 0, delta)
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

        # Eclair only syncs gossip from the (at most 5) channel peers with the
        # largest capacity. It syncs with query_short_channel_ids, which LDK
        # doesn't answer, and asks for no backlog of older gossip. An eclair
        # node without channels to other implementations only receives gossip
        # broadcast after it connected, so it may never learn the complete graph.
        def syncs_gossip(ln):
            if ln.impl != "eclair":
                return True
            peers = []
            for ch in self.channels:
                if ln.name in (ch["source"], ch["target"]):
                    peer = ch["target"] if ch["source"] == ln.name else ch["source"]
                    peers.append((ch["capacity"], peer))
            sync_peers = sorted(peers, reverse=True)[:5]
            return any(self.lns[peer].impl != "ldk" for _, peer in sync_peers)

        gossip_lns = [ln for ln in self.lns.values() if syncs_gossip(ln)]
        for ln in self.lns.values():
            if ln not in gossip_lns:
                self.log.info(
                    f"Not checking graph of eclair node {ln.name} without channels "
                    "to a node it can sync gossip from (any but LDK)"
                )

        self.log.info("Waiting for channel announcement gossip...")

        # Channel count in each node's graph, to detect when gossip stalls
        graph_counts = {}

        def ln_all_chs(self, ln):
            expected = len(self.channels)
            actual = 0
            while actual != expected:
                try:
                    actual = len(ln.graph()["edges"])
                    graph_counts[ln.name] = actual
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

        ch_ann_threads = [threading.Thread(target=ln_all_chs, args=(self, ln)) for ln in gossip_lns]
        for thread in ch_ann_threads:
            sleep(0.25)
            thread.start()

        # If no graph has grown for a while, reconnect nodes to their channel peers:
        # - An LDK node can end up never announcing a channel because the exchange
        #   of announcement_signatures with its peer didn't complete. Reconnecting
        #   makes both sides resend them.
        # - Eclair only runs a full gossip sync with a channel peer on connection.
        uris_by_pubkey = {uri.split("@")[0]: uri for uri in ln_uris.values()}
        last_counts = None
        last_progress = time()
        while any(thread.is_alive() for thread in ch_ann_threads):
            sleep(5)
            counts = dict(graph_counts)
            if counts != last_counts:
                last_counts = counts
                last_progress = time()
                continue
            if time() - last_progress < GOSSIP_STALL_TIMEOUT:
                continue
            self.log.info(
                f"Channel gossip stalled for {GOSSIP_STALL_TIMEOUT} seconds, "
                "reconnecting LDK nodes and incomplete eclair nodes to their channel peers..."
            )
            reconnect_threads = []
            for ln in self.lns.values():
                # An LDK node's own graph may be complete while the rest of the
                # network misses its channel updates
                incomplete = last_counts.get(ln.name, 0) < len(self.channels)
                if ln.impl == "ldk" or (ln.impl == "eclair" and ln in gossip_lns and incomplete):
                    t = threading.Thread(target=ln.reconnect_channel_peers, args=(uris_by_pubkey,))
                    t.start()
                    reconnect_threads.append(t)
            all(thread.join() is None for thread in reconnect_threads)
            last_progress = time()

        all(thread.join() is None for thread in ch_ann_threads)
        self.log.info("All LN nodes have complete graph")

        ##
        # UPDATE CHANNEL POLICIES
        ##
        self.log.info("Updating channel policies...")

        def update_policy(self, ln, outpoint, policy, capacity):
            self.log.info(f"Sending update from {ln.name} for channel with outpoint: {outpoint}")
            txid_hex, output_index = outpoint.split(":")
            res = None
            while res is None:
                try:
                    res = ln.update(txid_hex, policy, capacity, int(output_index))
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
                        ch["outpoint"],
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
                        ch["outpoint"],
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
                    # If this fails we have a bigger issue.
                    # Eclair does not report capacity of channels in its graph.
                    if "capacity" in actual_ch:
                        assert int(actual_ch["capacity"]) == capacity, (
                            f"LN {ln.name} graph capacity mismatch:\n actual: {actual_ch['capacity']}\n expected: {capacity}"
                        )

                    # Policies were not defined in network.yaml
                    if "source_policy" not in expected_ch or "target_policy" not in expected_ch:
                        continue

                    # Only LND reports both channel policies in its graph
                    if ln.impl != "lnd":
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
            threading.Thread(target=matching_graph, args=(self, expected, ln)) for ln in gossip_lns
        ]
        for thread in policy_threads:
            sleep(0.25)
            thread.start()

        all(thread.join() is None for thread in policy_threads)
        if thread_errors:
            raise Exception(f"{len(thread_errors)} ln_init thread(s) failed: {thread_errors}")
        self.log.info("All LN nodes have matching graph!")


def main():
    LNInit("").main()


if __name__ == "__main__":
    main()
