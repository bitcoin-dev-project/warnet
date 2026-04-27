import time

from commander import Commander, WARNET
from btcd_framework import BtcdRPC, BtcdRPCError


class BtcdRpcTest(Commander):
    def set_test_params(self):
        self.num_nodes = 1 
        self.mining_addr = "Sh6VJ4TabWtfBm9kvLWPzj8WGNsMmtyaGF"

    def add_options(self, parser):
        parser.description = (
            "Validate the BtcdRPC JSON-RPC interface against a live btcd network"
        )
        parser.usage = "warnet run /path/to/btcd_rpc_test.py"


    def _btcd_nodes(self) -> list[BtcdRPC]:
        nodes = []
        for tank in WARNET["tanks"]:
            impl = tank.get("implementation", "bitcoincore")
            if impl != "btcd":
                self.log.warning(
                    f"Skipping tank {tank['tank']} (implementation={impl})"
                )
                continue

            node = BtcdRPC(
                host=tank["rpc_host"],
                port=tank["rpc_port"],
                user=tank["rpc_user"],
                password=tank["rpc_password"],
            )
            node._tank_name = tank["tank"]

            node._p2p_port = tank.get("p2p_port", 18444)
            nodes.append(node)
        return nodes

    def _assert(self, condition: bool, msg: str):
        if not condition:
            self.log.error(f"FAIL: {msg}")
            raise AssertionError(msg)
        self.log.info(f"PASS: {msg}")


    def test_connection_and_basic_info(self, nodes: list[BtcdRPC]):
        self.log.info("=== Test 1: Connection & basic info ===")
        for node in nodes:
            count = node.getblockcount()
            self._assert(
                isinstance(count, int) and count >= 0,
                f"{node._tank_name}: getblockcount() = {count}",
            )

            info = node.getinfo()
            self._assert(
                isinstance(info, dict) and "version" in info,
                f"{node._tank_name}: getinfo() has 'version' field",
            )
            self.log.info(
                f"  {node._tank_name}: height={count}, version={info['version']}"
            )

    def test_peer_connectivity(self, nodes: list[BtcdRPC]):
        self.log.info("=== Test 2: Peer connectivity ===")
        for node in nodes:
            peers = node.getpeerinfo()
            self._assert(
                isinstance(peers, list) and len(peers) > 0,
                f"{node._tank_name}: getpeerinfo() has {len(peers)} peer(s)",
            )
            for peer in peers:
                self.log.info(
                    f"  {node._tank_name} ← peer addr={peer.get('addr')} "
                    f"version={peer.get('version')}"
                )

    def test_block_generation(self, nodes: list[BtcdRPC]):
        self.log.info("=== Test 3: Block generation ===")
        miner = nodes[0]
        height_before = miner.getblockcount()
        self.log.info(f"  Height before generate: {height_before}")

        NUM_BLOCKS = 5
        hashes = miner.generate(NUM_BLOCKS)
        self._assert(
            isinstance(hashes, list) and len(hashes) == NUM_BLOCKS,
            f"generate({NUM_BLOCKS}) returned a list of {NUM_BLOCKS} block hash(es)",
        )
        self.log.info(f"  First new block: {hashes[0]}")

        height_after = miner.getblockcount()
        self._assert(
            height_after == height_before + NUM_BLOCKS,
            f"Block height increased from {height_before} to {height_after} (+{NUM_BLOCKS})",
        )

        self.log.info("  Waiting for all nodes to sync...")

        time.sleep(3)
        for node in nodes[1:]:
            if node.getblockcount() < height_after:
                self.log.info(f"  Triggering sync on {node._tank_name} from {miner._tank_name}")
                node.force_sync_from(miner)

        SYNC_TIMEOUT = 30
        for i in range(SYNC_TIMEOUT):
            heights = {n._tank_name: n.getblockcount() for n in nodes}
            if all(h == height_after for h in heights.values()):
                break
            time.sleep(1)

        for node in nodes:
            synced_height = node.getblockcount()
            self._assert(
                synced_height == height_after,
                f"{node._tank_name}: synced to height {synced_height} (expected {height_after})",
            )

    def test_getblock_and_getblockhash(self, nodes: list[BtcdRPC]):
        self.log.info("=== Test 4: getblock / getblockhash ===")
        node = nodes[0]
        height = node.getblockcount()

        block_hash = node.getblockhash(height)
        self._assert(
            isinstance(block_hash, str) and len(block_hash) == 64,
            f"getblockhash({height}) returned a valid 64-char hex string",
        )

        block = node.getblock(block_hash, 1)
        self._assert(
            isinstance(block, dict) and block.get("hash") == block_hash,
            "getblock(hash, 1) returned object whose 'hash' matches",
        )
        self._assert(
            block.get("height") == height,
            f"Block height field matches ({block.get('height')} == {height})",
        )
        self.log.info(
            f"  Block {height}: txns={len(block.get('tx', []))}, "
            f"size={block.get('size')} bytes"
        )

    def test_raw_transaction_roundtrip(self, nodes: list[BtcdRPC]):
        self.log.info("=== Test 5: Raw transaction round-trip ===")
        node = nodes[0]

        genesis_hash = node.getblockhash(0)
        genesis_block = node.getblock(genesis_hash, 1)
        coinbase_txid = genesis_block["tx"][0]

        raw = node.getrawtransaction(coinbase_txid, 0)
        self._assert(
            isinstance(raw, str) and len(raw) > 0,
            "getrawtransaction(txid, verbose=0) returned a hex string",
        )

        decoded = node.decoderawtransaction(raw)
        self._assert(
            isinstance(decoded, dict) and decoded.get("txid") == coinbase_txid,
            "decoderawtransaction round-trip: decoded txid matches original",
        )
        self.log.info(
            f"  Coinbase tx: {coinbase_txid[:16]}…  "
            f"vin={len(decoded.get('vin', []))} "
            f"vout={len(decoded.get('vout', []))}"
        )

    def test_mempool(self, nodes: list[BtcdRPC]):
        self.log.info("=== Test 6: Mempool ===")
        node = nodes[0]

        info = node.getmempoolinfo()
        self._assert(
            isinstance(info, dict) and "size" in info and "bytes" in info,
            "getmempoolinfo() has 'size' and 'bytes' fields",
        )
        self.log.info(f"  Mempool: {info['size']} txns, {info['bytes']} bytes")

        txns = node.getrawmempool(False)
        self._assert(
            isinstance(txns, list),
            f"getrawmempool(verbose=False) returned a list ({len(txns)} items)",
        )

    def test_btcd_extensions(self, nodes: list[BtcdRPC]):
        self.log.info("=== Test 7: btcd extension methods ===")
        node = nodes[0]

        best = node.getbestblock()
        self._assert(
            isinstance(best, dict) and "hash" in best and "height" in best,
            "getbestblock() has 'hash' and 'height'",
        )
        self.log.info(
            f"  getbestblock: height={best['height']} hash={best['hash'][:16]}…"
        )

        net_id = node.getcurrentnet()
        self._assert(
            isinstance(net_id, int),
            f"getcurrentnet() returned numeric network ID: {net_id}",
        )

        ver = node.version()
        self._assert(
            isinstance(ver, dict) and "btcdjsonrpcapi" in ver,
            "version() has 'btcdjsonrpcapi' key",
        )
        self.log.info(
            f"  API version: {ver['btcdjsonrpcapi'].get('versionstring')}"
        )

    def run_test(self):
        nodes = self._btcd_nodes()
        self._assert(len(nodes) > 0, f"Found {len(nodes)} btcd node(s) in the network")
        self.log.info(
            f"Running tests against {len(nodes)} btcd node(s): "
            + ", ".join(n._tank_name for n in nodes)
        )

        self.test_connection_and_basic_info(nodes)
        self.test_peer_connectivity(nodes)
        self.test_block_generation(nodes)
        self.test_getblock_and_getblockhash(nodes)
        self.test_raw_transaction_roundtrip(nodes)
        self.test_mempool(nodes)
        self.test_btcd_extensions(nodes)

        self.log.info("=== All tests passed ===")


def main():
    BtcdRpcTest("").main()


if __name__ == "__main__":
    main()
