#!/usr/bin/env python3
import json
from time import sleep
from warnet.test_framework_bridge import WarnetTestFramework
from scenarios.utils import ensure_miner

def cli_help():
    return "Fund LN wallets and open channels"


class LNInit(WarnetTestFramework):
    def set_test_params(self):
        self.num_nodes = None

    def run_test(self):
        self.log.info("Get LN nodes and wallet addresses")
        recv_addrs = []
        for tank in self.warnet.tanks:
            if tank.lnnode is not None:
                recv_addrs.append(tank.lnnode.getnewaddress())

        self.log.info("Fund LN wallets")
        miner = ensure_miner(self.nodes[3])
        addr = miner.getnewaddress()
        self.generatetoaddress(self.nodes[3], 110, addr)
        for addr in recv_addrs:
            miner.sendtoaddress(addr, 50)
        self.generatetoaddress(self.nodes[3], 1, addr)

        self.log.info("Open channels")
        # TODO: This might belong in Warnet class as connect_ln_edges()
        #       but that would need to ensure spendable funds first.
        #       For now we consider this scenario "special".
        opening_txs = []
        ln_edges = []
        for edge in self.warnet.graph.edges(data=True):
            (src, dst, data) = edge
            if "channel" in data:
                src_node = self.warnet.get_ln_node_from_tank(src)
                assert src_node is not None
                assert self.warnet.get_ln_node_from_tank(dst) is not None
                ln_edges.append(edge)
                tx = src_node.open_channel_to_tank(dst, data["channel"])["funding_txid"]
                opening_txs.append(tx)


        self.log.info("Waiting for all channel open txs in mempool")
        while True:
            all_set = True
            mp = self.nodes[3].getrawmempool()
            for tx in opening_txs:
                if tx not in mp:
                    all_set = False
            if all_set:
                break
            sleep(2)

        self.log.info("Confirming channel opens")
        self.generatetoaddress(self.nodes[3], 6, addr)

        self.log.info("Waiting for graph gossip sync")
        while True:
            all_set = True
            for tank in self.warnet.tanks:
                if tank.lnnode is not None:
                    edges = json.loads(tank.lnnode.lncli("describegraph"))["edges"]
                    if len(edges) != len(ln_edges):
                        all_set = False
            if all_set:
                break
            sleep(2)

        self.log.info(f"Warnet LN ready with {len(recv_addrs)} nodes and {len(ln_edges)} channels.")

if __name__ == "__main__":
    LNInit().main()
