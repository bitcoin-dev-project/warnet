#!/usr/bin/env python3
from collections import defaultdict
from time import sleep

from test_framework.messages import CInv, msg_getdata
from test_framework.p2p import P2PInterface
from warnet.test_framework_bridge import WarnetTestFramework


def cli_help():
    return "Run P2P GETDATA test"


class P2PStoreBlock(P2PInterface):
    def __init__(self):
        super().__init__()
        self.blocks = defaultdict(int)

    def on_block(self, message):
        message.block.calc_sha256()
        self.blocks[message.block.sha256] += 1


class GetdataTest(WarnetTestFramework):
    def set_test_params(self):
        self.num_nodes = 1

    def run_test(self):
        while not self.warnet.network_connected():
            self.log.info("Waiting for complete network connection...")
            sleep(5)
        self.log.info("Network connected")

        self.log.info("Adding the p2p connection")

        p2p_block_store = self.nodes[0].add_p2p_connection(
            P2PStoreBlock(), dstaddr=self.warnet.tanks[0].ipv4, dstport=18444
        )

        self.log.info("test that an invalid GETDATA doesn't prevent processing of future messages")

        # Send invalid message and verify that node responds to later ping
        invalid_getdata = msg_getdata()
        invalid_getdata.inv.append(CInv(t=0, h=0))  # INV type 0 is invalid.
        p2p_block_store.send_and_ping(invalid_getdata)

        # Check getdata still works by fetching tip block
        best_block = int(self.nodes[0].getbestblockhash(), 16)
        good_getdata = msg_getdata()
        good_getdata.inv.append(CInv(t=2, h=best_block))
        p2p_block_store.send_and_ping(good_getdata)
        p2p_block_store.wait_until(lambda: p2p_block_store.blocks[best_block] == 1)


if __name__ == "__main__":
    GetdataTest().main()
