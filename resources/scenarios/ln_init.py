#!/usr/bin/env python3

import threading
from time import sleep

from commander import Commander


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

        def tank_connected(self, tank):
            while True:
                peers = tank.getpeerinfo()
                count = sum(
                    1
                    for peer in peers
                    if peer.get("connection_type") == "manual" or peer.get("addnode") is True
                )
                self.log.info(f"Tank {tank.tank} connected to {count}/{tank.init_peers} peers")
                if count >= tank.init_peers:
                    break
                else:
                    sleep(1)

        conn_threads = [
            threading.Thread(target=tank_connected, args=(self, tank)) for tank in self.nodes
        ]
        for thread in conn_threads:
            thread.start()

        all(thread.join() is None for thread in conn_threads)
        self.log.info("Network connected")

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

        def get_ln_addr(self, name, ln):
            while True:
                res = ln.newaddress()
                if "address" in res:
                    addr = res["address"]
                    ln_addrs.append(addr)
                    self.log.info(f"Got wallet address {addr} from {name}")
                    break
                else:
                    self.log.info(
                        f"Couldn't get wallet address from {name}:\n  {res}\n  wait and retry..."
                    )
                    sleep(1)

        addr_threads = [
            threading.Thread(target=get_ln_addr, args=(self, name, ln))
            for name, ln in self.lns.items()
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

        def confirm_ln_balance(self, name, ln):
            bal = 0
            while True:
                bal = ln.walletbalance()
                if bal >= (split * 100000000):
                    self.log.info(f"LN node {name} confirmed funds")
                    break
                sleep(1)

        fund_threads = [
            threading.Thread(target=confirm_ln_balance, args=(self, name, ln))
            for name, ln in self.lns.items()
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

        def get_ln_uri(self, name, ln):
            uri = None
            while True:
                uri = ln.uri()
                if uri:
                    ln_uris[name] = uri
                    self.log.info(f"LN node {name} has URI {uri}")
                    break
                sleep(1)

        uri_threads = [
            threading.Thread(target=get_ln_uri, args=(self, name, ln))
            for name, ln in self.lns.items()
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
                        self.log.info(
                            f"Unexpected response attempting to connect {pair[0].name} -> {pair[1].name}:\n  {res}\n  ABORTING"
                        )
                        break

        p2p_threads = [
            threading.Thread(target=connect_ln, args=(self, pair)) for pair in connections
        ]
        for thread in p2p_threads:
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
            # TODO: if "id" not in ch ...
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
                    pk=self.hex_to_b64(tgt_pk),
                    local_amt=ch["local_amt"],
                    push_amt=ch["push_amt"],
                    fee_rate=fee_rate,
                )
                if "result" not in res:
                    self.log.info(
                        "Unexpected channel open response:\n  "
                        + f"From {ch['source']} -> {ch['target']} fee_rate={fee_rate}\n  "
                        + f"{res}"
                    )
                else:
                    txid = self.b64_to_hex(res["result"]["chan_pending"]["txid"], reverse=True)
                    ch["txid"] = txid
                    self.log.info(
                        f"Channel open {ch['source']} -> {ch['target']}\n  "
                        + f"outpoint={txid}:{res['result']['chan_pending']['output_index']}\n  "
                        + f"expected channel id: {ch['id']}"
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
                assert ch["id"]["block"] == block_height
                assert block_txs[ch["id"]["index"]] == ch["txid"]
            self.log.info("👍")

        gen(5)
        self.log.info(f"Confirmed {len(self.channels)} total channel opens")

        # self.log.info("Updating channel policies")
        # for edge, chan_pt in chan_opens:
        #     (src, dst, key, data) = edge
        #     if "target_policy" in data:
        #         target_node = self.warnet.get_ln_node_from_tank(dst)
        #         target_node.update_channel_policy(chan_pt, data["target_policy"])
        #     if "source_policy" in data:
        #         source_node = self.warnet.get_ln_node_from_tank(src)
        #         source_node.update_channel_policy(chan_pt, data["source_policy"])

        # while True:
        #     self.log.info("Waiting for all channel policies to match")
        #     score = 0
        #     for tank_index, me in enumerate(ln_nodes):
        #         you = (tank_index + 1) % len(ln_nodes)
        #         my_channels = self.warnet.tanks[me].lnnode.get_graph_channels()
        #         your_channels = self.warnet.tanks[you].lnnode.get_graph_channels()
        #         match = True
        #         for _chan_index, my_chan in enumerate(my_channels):
        #             your_chan = [
        #                 chan
        #                 for chan in your_channels
        #                 if chan.short_chan_id == my_chan.short_chan_id
        #             ][0]
        #             if not your_chan:
        #                 print(f"Channel policy missing for channel: {my_chan.short_chan_id}")
        #                 match = False
        #                 break

        #             try:
        #                 if not my_chan.channel_match(your_chan):
        #                     print(
        #                         f"Channel policy doesn't match between tanks {me} & {you}: {my_chan.short_chan_id}"
        #                     )
        #                     match = False
        #                     break
        #             except Exception as e:
        #                 print(f"Error comparing channel policies: {e}")
        #                 print(
        #                     f"Channel policy doesn't match between tanks {me} & {you}: {my_chan.short_chan_id}"
        #                 )
        #                 match = False
        #                 break
        #         if match:
        #             print(f"All channel policies match between tanks {me} & {you}")
        #             score += 1
        #     print(f"Score: {score} / {len(ln_nodes)}")
        #     if score == len(ln_nodes):
        #         break
        #     sleep(5)

        # self.log.info(
        #     f"Warnet LN ready with {len(recv_addrs)} nodes and {len(chan_opens)} channels."
        # )


def main():
    LNInit().main()


if __name__ == "__main__":
    main()
