#!/usr/bin/env python3
from collections import defaultdict

# The base class exists inside the commander container
try:
    from commander import Commander
except Exception:
    from resources.scenarios.commander import Commander


from test_framework.messages import CInv, msg_getdata
from test_framework.p2p import P2PInterface


def cli_help():
    return "Run P2P GETDATA test"


class P2PStoreBlock(P2PInterface):
    def __init__(self):
        super().__init__()
        self.blocks = defaultdict(int)

    def on_block(self, message):
        message.block.calc_sha256()
        self.blocks[message.block.sha256] += 1


class GetdataTest(Commander):
    def set_test_params(self):
        self.num_nodes = 1

    def run_test(self):
        self.log.info("Adding the p2p connection")

        p2p_block_store = self.nodes[0].add_p2p_connection(
            P2PStoreBlock(), dstaddr=self.nodes[0].rpchost, dstport=18444
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
