#!/usr/bin/env python3

from time import sleep

from commander import Commander


class LNInit(Commander):
    def set_test_params(self):
        self.num_nodes = None

    def add_options(self, parser):
        parser.description = "Fund LN wallets and open channels"
        parser.usage = "warnet run /path/to/ln_init.py"

    def run_test(self):
        self.log.info("Lock out of IBD")
        miner = self.ensure_miner(self.nodes[0])
        miner_addr = miner.getnewaddress()
        self.generatetoaddress(self.nodes[0], 1, miner_addr, sync_fun=self.no_op)

        self.log.info("Get LN nodes and wallet addresses")
        ln_nodes = []
        recv_addrs = []
        for tank in self.warnet.tanks:
            if tank.lnnode is not None:
                recv_addrs.append(tank.lnnode.getnewaddress())
                ln_nodes.append(tank.index)

        self.log.info("Fund LN wallets")
        miner = self.ensure_miner(self.nodes[0])
        miner_addr = miner.getnewaddress()
        # 298 block base
        self.generatetoaddress(self.nodes[0], 297, miner_addr, sync_fun=self.no_op)
        # divvy up the goods
        split = (miner.getbalance() - 1) // len(recv_addrs)
        sends = {}
        for addr in recv_addrs:
            sends[addr] = split
        miner.sendmany("", sends)
        # confirm funds in block 299
        self.generatetoaddress(self.nodes[0], 1, miner_addr, sync_fun=self.no_op)

        self.log.info(
            f"Waiting for funds to be spendable: {split} BTC each for {len(recv_addrs)} LN nodes"
        )

        def funded_lnnodes():
            for tank in self.warnet.tanks:
                if tank.lnnode is None:
                    continue
                if int(tank.lnnode.get_wallet_balance()) < (split * 100000000):
                    return False
            return True

        self.wait_until(funded_lnnodes, timeout=5 * 60)

        ln_nodes_uri = ln_nodes.copy()
        while len(ln_nodes_uri) > 0:
            self.log.info(
                f"Waiting for all LN nodes to have URI, LN nodes remaining: {ln_nodes_uri}"
            )
            for index in ln_nodes_uri:
                lnnode = self.warnet.tanks[index].lnnode
                if lnnode.getURI():
                    ln_nodes_uri.remove(index)
            sleep(5)

        self.log.info("Adding p2p connections to LN nodes")
        for edge in self.warnet.graph.edges(data=True):
            (src, dst, data) = edge
            # Copy the L1 p2p topology (where applicable) to L2
            # so we get a more robust p2p graph for lightning
            if (
                "channel_open" not in data
                and self.warnet.tanks[src].lnnode
                and self.warnet.tanks[dst].lnnode
            ):
                self.warnet.tanks[src].lnnode.connect_to_tank(dst)

        # Start confirming channel opens in block 300
        self.log.info("Opening channels, one per block")
        chan_opens = []
        edges = self.warnet.graph.edges(data=True, keys=True)
        edges = sorted(edges, key=lambda edge: edge[2])
        for edge in edges:
            (src, dst, key, data) = edge
            if "channel_open" in data:
                src_node = self.warnet.get_ln_node_from_tank(src)
                assert src_node is not None
                assert self.warnet.get_ln_node_from_tank(dst) is not None
                self.log.info(f"opening channel {src}->{dst}")
                chan_pt = src_node.open_channel_to_tank(dst, data["channel_open"])
                # We can guarantee deterministic short channel IDs as long as
                # the change output is greater than the channel funding output,
                # which will then be output 0
                assert chan_pt[64:] == ":0"
                chan_opens.append((edge, chan_pt))
                self.log.info(f"  pending channel point: {chan_pt}")
                self.wait_until(
                    lambda chan_pt=chan_pt: chan_pt[:64] in self.nodes[0].getrawmempool()
                )
                self.generatetoaddress(self.nodes[0], 1, miner_addr)
                assert chan_pt[:64] not in self.nodes[0].getrawmempool()
                height = self.nodes[0].getblockcount()
                self.log.info(f"  confirmed in block {height}")
                self.log.info(
                    f"  channel_id should be: {int.from_bytes(height.to_bytes(3, 'big') + (1).to_bytes(3, 'big') + (0).to_bytes(2, 'big'), 'big')}"
                )

        # Ensure all channel opens are sufficiently confirmed
        self.generatetoaddress(self.nodes[0], 10, miner_addr, sync_fun=self.no_op)
        ln_nodes_gossip = ln_nodes.copy()
        while len(ln_nodes_gossip) > 0:
            self.log.info(f"Waiting for graph gossip sync, LN nodes remaining: {ln_nodes_gossip}")
            for index in ln_nodes_gossip:
                lnnode = self.warnet.tanks[index].lnnode
                count_channels = len(lnnode.get_graph_channels())
                count_graph_nodes = len(lnnode.get_graph_nodes())
                if count_channels == len(chan_opens) and count_graph_nodes == len(ln_nodes):
                    ln_nodes_gossip.remove(index)
                else:
                    self.log.info(
                        f" node {index} not synced (channels: {count_channels}/{len(chan_opens)}, nodes: {count_graph_nodes}/{len(ln_nodes)})"
                    )
            sleep(5)

        self.log.info("Updating channel policies")
        for edge, chan_pt in chan_opens:
            (src, dst, key, data) = edge
            if "target_policy" in data:
                target_node = self.warnet.get_ln_node_from_tank(dst)
                target_node.update_channel_policy(chan_pt, data["target_policy"])
            if "source_policy" in data:
                source_node = self.warnet.get_ln_node_from_tank(src)
                source_node.update_channel_policy(chan_pt, data["source_policy"])

        while True:
            self.log.info("Waiting for all channel policies to match")
            score = 0
            for tank_index, me in enumerate(ln_nodes):
                you = (tank_index + 1) % len(ln_nodes)
                my_channels = self.warnet.tanks[me].lnnode.get_graph_channels()
                your_channels = self.warnet.tanks[you].lnnode.get_graph_channels()
                match = True
                for _chan_index, my_chan in enumerate(my_channels):
                    your_chan = [
                        chan
                        for chan in your_channels
                        if chan.short_chan_id == my_chan.short_chan_id
                    ][0]
                    if not your_chan:
                        print(f"Channel policy missing for channel: {my_chan.short_chan_id}")
                        match = False
                        break

                    try:
                        if not my_chan.channel_match(your_chan):
                            print(
                                f"Channel policy doesn't match between tanks {me} & {you}: {my_chan.short_chan_id}"
                            )
                            match = False
                            break
                    except Exception as e:
                        print(f"Error comparing channel policies: {e}")
                        print(
                            f"Channel policy doesn't match between tanks {me} & {you}: {my_chan.short_chan_id}"
                        )
                        match = False
                        break
                if match:
                    print(f"All channel policies match between tanks {me} & {you}")
                    score += 1
            print(f"Score: {score} / {len(ln_nodes)}")
            if score == len(ln_nodes):
                break
            sleep(5)

        self.log.info(
            f"Warnet LN ready with {len(recv_addrs)} nodes and {len(chan_opens)} channels."
        )


def main():
    LNInit().main()


if __name__ == "__main__":
    main()
