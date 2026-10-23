#!/usr/bin/env python3

import json
import os
import sys
from pathlib import Path

import pexpect
from test_base import TestBase

from warnet.process import stream_command

# Matches network.yaml
IMPLS = {
    "tank-0000-ln": "lnd",
    "tank-0001-ln": "eclair",
    "tank-0002-ln": "cln",
    "tank-0003-ln": "eclair",
    "tank-0004-ln": "eclair",
    "tank-0005-ln": "ldk",
    "tank-0006-ln": "ldk",
}
# (block, index, source, target) opened by ln_init
CHANNELS = [
    (500, 1, "tank-0000-ln", "tank-0001-ln"),
    (500, 2, "tank-0001-ln", "tank-0002-ln"),
    (501, 1, "tank-0002-ln", "tank-0003-ln"),
    (502, 1, "tank-0003-ln", "tank-0000-ln"),
    (503, 1, "tank-0005-ln", "tank-0002-ln"),
    (503, 2, "tank-0000-ln", "tank-0006-ln"),
    (503, 3, "tank-0002-ln", "tank-0000-ln"),
    (503, 4, "tank-0005-ln", "tank-0003-ln"),
]


class LNMixedTest(TestBase):
    def __init__(self):
        super().__init__()
        self.network_dir = Path(os.path.dirname(__file__)) / "data" / "ln_mixed"

    def run_test(self):
        try:
            # Wait for all nodes to wake up. ln_init will start automatically
            self.setup_network()

            self.test_cli()
            self.test_channels()

            # Direct payments
            self.pay_invoice(sender="tank-0000-ln", recipient="tank-0001-ln")
            self.pay_invoice(sender="tank-0001-ln", recipient="tank-0002-ln")
            # Multi-hop payments routed through every implementation
            self.pay_invoice(sender="tank-0002-ln", recipient="tank-0000-ln")
            self.pay_invoice(sender="tank-0003-ln", recipient="tank-0002-ln")
            # LDK paying, receiving and routing
            self.pay_invoice(sender="tank-0002-ln", recipient="tank-0005-ln")
            self.pay_invoice(sender="tank-0005-ln", recipient="tank-0000-ln")
            self.pay_invoice(sender="tank-0003-ln", recipient="tank-0006-ln")

            self.test_data_persistence()
        finally:
            self.cleanup()

    def setup_network(self):
        self.log.info("Setting up network")
        stream_command(f"warnet deploy {self.network_dir}")

    def rpc(self, ln, cmd):
        return json.loads(self.warnet(f"ln rpc {ln} {cmd}"))

    def test_cli(self):
        self.log.info("Testing warnet ln commands with eclair and ldk")
        for ln in ["tank-0001-ln", "tank-0003-ln", "tank-0004-ln"]:
            info = self.rpc(ln, "getinfo")
            assert self.warnet(f"ln pubkey {ln}") == info["nodeId"]
            assert self.warnet(f"ln host {ln}") == f"{ln}.default"
        for ln in ["tank-0005-ln", "tank-0006-ln"]:
            info = self.rpc(ln, "get-node-info")
            assert self.warnet(f"ln pubkey {ln}") == info["node_id"]
            assert self.warnet(f"ln host {ln}") == f"{ln}.default"

    def test_channels(self):
        self.log.info("Checking channels opened by ln_init")

        # lnd and ldk use the integer encoding of short channel IDs
        def lnd_scid(chan_id):
            chan_id = int(chan_id)
            return (chan_id >> 40, (chan_id >> 16) & 0xFFFFFF)

        def eclair_scid(scid):
            block, index, _ = scid.split("x")
            return (int(block), int(index))

        expected = sorted((block, index) for block, index, _, _ in CHANNELS)

        def graphs_complete():
            lnd = self.rpc("tank-0000-ln", "describegraph")["edges"]
            if sorted(lnd_scid(ch["channel_id"]) for ch in lnd) != expected:
                return False
            for ln in ["tank-0001-ln", "tank-0003-ln"]:
                eclair = self.rpc(ln, "allchannels")
                if sorted(eclair_scid(ch["shortChannelId"]) for ch in eclair) != expected:
                    return False
            for ln in ["tank-0005-ln", "tank-0006-ln"]:
                ldk = self.rpc(ln, "graph-list-channels")["short_channel_ids"]
                if sorted(lnd_scid(scid) for scid in ldk) != expected:
                    return False
            cln = self.rpc("tank-0002-ln", "listchannels")["channels"]
            return len([ch for ch in cln if ch["direction"] == 1]) == len(CHANNELS)

        self.wait_for_predicate(graphs_complete)

        # Eclair only syncs gossip from peers it has channels with. Without
        # channels it only receives its peers' announcements of their own
        # channels, so it may have an incomplete graph (but never a wrong one).
        partial = sorted(
            eclair_scid(ch["shortChannelId"]) for ch in self.rpc("tank-0004-ln", "allchannels")
        )
        self.log.info(
            f"tank-0004-ln without channels has {len(partial)} of {len(expected)} channels"
        )
        assert set(partial) <= set(expected), partial

    def create_invoice(self, ln, sats, label):
        if IMPLS[ln] == "lnd":
            inv = self.rpc(ln, f"addinvoice --amt {sats} --memo {label}")
            return inv["payment_request"], inv["r_hash"]
        if IMPLS[ln] == "cln":
            inv = self.rpc(ln, f"invoice {sats * 1000} {label} {label}")
            return inv["bolt11"], inv["payment_hash"]
        if IMPLS[ln] == "eclair":
            inv = self.rpc(ln, f"createinvoice --amountMsat={sats * 1000} --description={label}")
            return inv["serialized"], inv["paymentHash"]
        inv = self.rpc(ln, f"bolt11-receive {sats}sat --description {label}")
        return inv["invoice"], inv["payment_hash"]

    def pay(self, ln, invoice):
        if IMPLS[ln] == "lnd":
            return self.warnet(f"ln rpc {ln} payinvoice -f {invoice}")
        if IMPLS[ln] == "cln":
            return self.warnet(f"ln rpc {ln} pay {invoice}")
        if IMPLS[ln] == "eclair":
            return self.warnet(f"ln rpc {ln} payinvoice --invoice={invoice} --blocking=true")
        return self.warnet(f"ln rpc {ln} bolt11-send {invoice}")

    def is_paid(self, ln, payment_hash):
        if IMPLS[ln] == "lnd":
            return self.rpc(ln, f"lookupinvoice {payment_hash}")["state"] == "SETTLED"
        if IMPLS[ln] == "cln":
            invs = self.rpc(ln, f"listinvoices -k payment_hash={payment_hash}")["invoices"]
            return invs[0]["status"] == "paid"
        if IMPLS[ln] == "eclair":
            info = self.rpc(ln, f"getreceivedinfo --paymentHash={payment_hash}")
            return info["status"]["type"] == "received"
        # LDK only stores a received payment when it arrives, under an id
        # that isn't the payment hash, so look for the hash in all payments.
        payments = self.rpc(ln, "list-payments")["list"]
        return any(
            p["direction"] == "INBOUND"
            and p["status"] == "SUCCEEDED"
            and payment_hash in json.dumps(p["kind"])
            for p in payments
        )

    def pay_invoice(self, sender, recipient):
        self.log.info(
            f"Paying invoice {sender} ({IMPLS[sender]}) -> {recipient} ({IMPLS[recipient]})"
        )
        label = f"{sender}-to-{recipient}"
        invoice, payment_hash = self.create_invoice(recipient, 1000, label)
        assert not self.is_paid(recipient, payment_hash)

        # Retry since gossip about new channels may still be propagating
        def pay_and_check():
            if not self.is_paid(recipient, payment_hash):
                self.log.info(self.pay(sender, invoice))
            return self.is_paid(recipient, payment_hash)

        self.wait_for_predicate(pay_and_check, interval=10)

    def get_eclair_state(self, ln):
        return {
            "pub": self.rpc(ln, "getinfo")["nodeId"],
            "channels": sorted(ch["channelId"] for ch in self.rpc(ln, "channels")),
            "invs": self.rpc(ln, "listinvoices"),
        }

    def get_ldk_state(self, ln):
        return {
            "pub": self.rpc(ln, "get-node-info")["node_id"],
            "channels": sorted(
                ch["channel_id"] for ch in self.rpc(ln, "list-channels")["channels"]
            ),
            "pays": sorted(p["payment_id"] for p in self.rpc(ln, "list-payments")["list"]),
        }

    def test_data_persistence(self):
        self.log.info("Testing eclair and ldk data persistence")
        first = {
            # Persistence enabled
            "tank-0001-ln": self.get_eclair_state("tank-0001-ln"),
            "tank-0005-ln": self.get_ldk_state("tank-0005-ln"),
            # No persistence
            "tank-0003-ln": self.get_eclair_state("tank-0003-ln"),
            "tank-0006-ln": self.get_ldk_state("tank-0006-ln"),
        }

        self.log.info("Stopping network")
        session = pexpect.spawn("warnet down", encoding="utf-8", dimensions=(60, 200))
        session.logfile = sys.stdout
        session.expect("Do you want to bring down the running Warnet?", timeout=30)
        session.send("y")
        session.expect("Do you also want to delete all PVCs", timeout=5)
        session.send("n")
        session.expect("Warnet teardown process completed", timeout=300)

        self.log.info("Restarting...")
        self.setup_network()

        self.log.info("eclair tank 0001 should have restored persistent data")
        self.wait_for_predicate(
            lambda: self.get_eclair_state("tank-0001-ln") == first["tank-0001-ln"]
        )

        self.log.info("eclair tank 0003 should NOT have restored persistent data")
        second = self.get_eclair_state("tank-0003-ln")
        assert first["tank-0003-ln"] != second, first["tank-0003-ln"]
        assert first["tank-0003-ln"]["pub"] != second["pub"]

        self.log.info("ldk tank 0005 should have restored persistent data")
        self.wait_for_predicate(lambda: self.get_ldk_state("tank-0005-ln") == first["tank-0005-ln"])

        self.log.info("ldk tank 0006 should NOT have restored persistent data")
        second = self.get_ldk_state("tank-0006-ln")
        assert first["tank-0006-ln"]["pub"] != second["pub"], first["tank-0006-ln"]


if __name__ == "__main__":
    test = LNMixedTest()
    test.run_test()
