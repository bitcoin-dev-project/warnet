import time

from btcd_framework import BtcdRPC, BtcdRPCError
from commander import Commander, WARNET


class BtcdMiner(Commander):
    def set_test_params(self):
        self.num_nodes = 1 

    def add_options(self, parser):
        parser.description = "Mine blocks on a btcd network and log network status"
        parser.usage = "warnet run /path/to/btcd_miner.py [options]"
        parser.add_argument(
            "--blocks",
            dest="blocks",
            default=5,
            type=int,
            help="Blocks to generate per round (default: 5)",
        )
        parser.add_argument(
            "--interval",
            dest="interval",
            default=30,
            type=int,
            help="Seconds between rounds (default: 30)",
        )
        parser.add_argument(
            "--rounds",
            dest="rounds",
            default=3,
            type=int,
            help="Number of mining rounds, 0 = infinite (default: 3)",
        )

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

    def _network_status(self, nodes: list[BtcdRPC]) -> dict:
        status = {}
        for node in nodes:
            try:
                height = node.getblockcount()
                peers  = len(node.getpeerinfo())
                mempool = node.getmempoolinfo().get("size", 0)
                status[node._tank_name] = {
                    "height":  height,
                    "peers":   peers,
                    "mempool": mempool,
                }
            except Exception as exc:
                status[node._tank_name] = {"error": str(exc)}
        return status

    def _log_status(self, round_num: int, status: dict):
        self.log.info(
            f"┌─────────────────────────────────────────────────────────────┐"
        )
        self.log.info(
            f"│  Round {round_num:>3}  Network Status                                 │"
        )
        self.log.info(
            f"├──────────────┬──────────┬─────────┬───────────────────────────┤"
        )
        self.log.info(
            f"│  Node        │  Height  │  Peers  │  Mempool txs              │"
        )
        self.log.info(
            f"├──────────────┼──────────┼─────────┼───────────────────────────┤"
        )
        for name, data in status.items():
            if "error" in data:
                self.log.info(f"│  {name:<12}│  ERROR   │         │  {data['error'][:26]:<26} │")
            else:
                self.log.info(
                    f"│  {name:<12}│  {data['height']:>6}  │  {data['peers']:>5}  │  {data['mempool']:>5} txs                │"
                )
        self.log.info(
            f"└──────────────┴──────────┴─────────┴───────────────────────────┘"
        )

    def _propagate(self, nodes: list[BtcdRPC], miner: BtcdRPC, target_height: int):
        time.sleep(3)

        for node in nodes:
            if node is miner:
                continue
            if node.getblockcount() < target_height:
                node.force_sync_from(miner)

        timeout = 60
        for elapsed in range(timeout):
            heights = {n._tank_name: n.getblockcount() for n in nodes}
            if all(h >= target_height for h in heights.values()):
                self.log.info(
                    f"All nodes synced to height {target_height} "
                    f"in ~{elapsed}s"
                )
                return
            if elapsed % 10 == 0 and elapsed > 0:
                behind = {k: v for k, v in heights.items() if v < target_height}
                self.log.info(f"  Waiting for sync ({elapsed}s): {behind}")
            time.sleep(1)

        heights = {n._tank_name: n.getblockcount() for n in nodes}
        behind = {k: v for k, v in heights.items() if v < target_height}
        if behind:
            self.log.warning(
                f" Sync timeout after {timeout}s. Still behind: {behind}"
            )


    def run_test(self):
        nodes = self._btcd_nodes()
        if not nodes:
            self.log.error("No btcd nodes found in the network. Aborting.")
            return

        miner = nodes[0]
        self.log.info(
            f"btcd_miner: {len(nodes)} node(s) found — "
            f"miner={miner._tank_name} "
            f"[blocks={self.options.blocks}, interval={self.options.interval}s, "
            f"rounds={'inf' if self.options.rounds == 0 else self.options.rounds}]"
        )

        self.log.info("=== Initial network status ===")
        self._log_status(0, self._network_status(nodes))

        round_num = 0
        while True:
            round_num += 1
            if self.options.rounds > 0 and round_num > self.options.rounds:
                break

            self.log.info(
                f"=== Round {round_num}"
                + (f"/{self.options.rounds}" if self.options.rounds > 0 else "")
                + f": generating {self.options.blocks} block(s) on {miner._tank_name} ==="
            )

            try:
                before = miner.getblockcount()
                hashes = miner.generate(self.options.blocks)
                after  = miner.getblockcount()
                self.log.info(
                    f"  Mined {len(hashes)} block(s) — "
                    f"height {before} → {after}"
                )
                for h in hashes:
                    self.log.info(f"     {h}")
            except BtcdRPCError as exc:
                self.log.error(f"  generate() failed: {exc}")
                break

            self._propagate(nodes, miner, after)

            self._log_status(round_num, self._network_status(nodes))

            if self.options.rounds == 0 or round_num < self.options.rounds:
                time.sleep(self.options.interval)

        self.log.info("===>> btcd_miner finished")


def main():
    BtcdMiner("").main()


if __name__ == "__main__":
    main()
