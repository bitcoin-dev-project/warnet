#!/usr/bin/env python3

from warnet.test_framework_bridge import WarnetTestFramework
from scenarios.utils import ensure_miner


def cli_help():
    return ("Send a transaction using sensitive relay")


class MinerStd(WarnetTestFramework):
    def set_test_params(self):
        self.num_nodes = 11

    def run_test(self):
        # PR branch node
        test_node = self.nodes[10]
        test_wallet = ensure_miner(test_node)
        addr = test_wallet.getnewaddress()

        self.log.info("generating 110 blocks...")
        self.generatetoaddress(test_node, 110, addr)

        self.log.info("adding onion addresses from all peers...")
        for i in range(10):
            info = self.nodes[i].getnetworkinfo()
            for addr in info["localaddresses"]:
                if "onion" in addr["address"]:
                    self.log.info(f"adding {addr['address']}:{addr['port']}")
                    test_node.addpeeraddress(addr["address"], addr["port"])

        self.log.info("getting address from recipient...")
        # some other node
        recip = self.nodes[5]
        recip_wallet = ensure_miner(recip)
        recip_addr = recip_wallet.getnewaddress()

        self.log.info("sending transaction...")
        self.log.info(test_wallet.sendtoaddress(recip_addr, 0.5))


if __name__ == '__main__':
    MinerStd().main()
