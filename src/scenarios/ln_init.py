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
        lnd0 = self.warnet.tanks[0].lnnode
        lnd1 = self.warnet.tanks[1].lnnode
        lnd2 = self.warnet.tanks[2].lnnode
        adr0 = lnd0.getnewaddress()
        adr1 = lnd1.getnewaddress()
        adr2 = lnd2.getnewaddress()

        self.log.info("Fund LN wallets")
        miner = ensure_miner(self.nodes[3])
        addr = miner.getnewaddress()
        self.generatetoaddress(self.nodes[3], 110, addr)
        miner.sendtoaddress(adr0, 50)
        miner.sendtoaddress(adr1, 50)
        miner.sendtoaddress(adr2, 50)
        self.generatetoaddress(self.nodes[3], 1, addr)

        self.log.info("Open channels")
        tx0 = lnd0.open_channel_to_tank(1, 100000)["funding_txid"]
        tx1 = lnd1.open_channel_to_tank(2, 100000)["funding_txid"]

        self.log.info("Waiting for channel open tx in mempool")
        while True:
            mp = self.nodes[3].getrawmempool()
            if tx0 in mp and tx1 in mp:
                break
            sleep(2)

        self.log.info("Confirming channel opens")
        self.generatetoaddress(self.nodes[3], 6, addr)

        self.log.info("Waiting for graph gossip")
        while True:
            edges = json.loads(lnd0.lncli("describegraph"))["edges"]
            if len(edges) == 2:
                break
            sleep(2)

        self.log.info("Test LN payment")
        inv = json.loads(lnd2.lncli("addinvoice --amt=1234"))["payment_request"]
        self.log.info(inv)
        lnd0.lncli(f"payinvoice -f {inv}")

        self.log.info("Waiting for payment success")
        while True:
            invs = json.loads(lnd2.lncli("listinvoices"))["invoices"]
            if len(invs) > 0:
                if invs[0]["state"] == "SETTLED":
                    break
            sleep(2)

if __name__ == "__main__":
    LNInit().main()
