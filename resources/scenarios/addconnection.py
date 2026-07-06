#!/usr/bin/env python3
"""Open post-deploy peer connections via the addconnection RPC.

Warnet wires the per-node ``addnode`` topology into bitcoin.conf at startup.
This connections are flagged as manual, and don't allow testing some of the
connection-specific functionality (e.g. block-only).

Each ``addconnection`` entry may take any of these forms:

  * ``tank-0003``                     -> bare name, uses the default type
  * ``[tank-0003]``                   -> single-element list, uses the default type
  * ``[tank-0003, block-relay-only]`` -> explicit ``[peer, type]`` pair

``deploy.py`` ships the ``{tank: [entry, ...]}`` mapping into the commander pod
as ``/shared/connections.json`` and auto-runs this scenario whenever any node
declares an ``addconnection`` list.
"""

import json
import logging
import os
import threading
from time import monotonic, sleep

from commander import Commander

# Default location of the file containing the additional connections
CONNECTIONS_FILE = "/shared/connections.json"
# Default connection type if only a tank name is specified (instead of [tank, type] pair)
DEFAULT_CONNECTION_TYPE = "block-relay-only"
# Seconds to wait for a source tank's RPC to come up before issuing its connections.
RPC_READY_TIMEOUT = 60
# Seconds to wait for each tank's connections to show up in getpeerinfo.
CONNECT_TIMEOUT = 30


class AddConnection(Commander):
    def set_test_params(self):
        # Nodes are discovered from the cluster, not started by the framework.
        self.num_nodes = 1

    def add_options(self, parser):
        parser.description = (
            "Creates the addconnection edges shipped during deployment via the addconnection RPC."
        )
        parser.usage = "warnet run /path/to/addconnection.py [options]"
        parser.add_argument(
            "--connections-file",
            dest="connections_file",
            default=CONNECTIONS_FILE,
            help=f"Path to the JSON {{tank: [[peer, type], ...]}} mapping (default: {CONNECTIONS_FILE})",
        )
        parser.add_argument(
            "--default-connection-type",
            dest="default_connection_type",
            default=DEFAULT_CONNECTION_TYPE,
            help="Connection type for entries given as a bare tank name instead of a "
            f"[tank, type] pair (default: {DEFAULT_CONNECTION_TYPE})",
        )

    def run_test(self):
        path = self.options.connections_file
        if not os.path.exists(path):
            self.log.warning(f"{path} not found; no connections to open")
            return

        with open(path) as f:
            connections = json.load(f)

        total = sum(len(entries) for entries in connections.values())
        self.log.info(
            f"Opening {total} connections across {len(connections)} tanks via addconnection"
        )
        issued = self.create_connections(connections)
        self.verify_connections(issued)

    def _parse_entry(self, entry):
        """Return (peer_name, connection_type) for an addconnection entry. An entry
        is a [tank, type] pair; a bare tank name or a single-element [tank] list
        falls back to the default connection type."""
        if isinstance(entry, (list, tuple)):
            peer = entry[0]
            conn_type = entry[1] if len(entry) > 1 else self.options.default_connection_type
        else:
            peer = entry
            conn_type = self.options.default_connection_type
        return peer, conn_type

    def _wait_rpc_ready(self, node, tank):
        """Block until the tank's RPC answers or RPC_READY_TIMEOUT elapses.

        deploy runs this scenario as soon as the commander pod is up, which can
        race ahead of a tank's bitcoind still starting; addconnection would then
        fail with a bare "Connection refused". Returns True once RPC responds."""
        deadline = monotonic() + RPC_READY_TIMEOUT
        while monotonic() < deadline:
            try:
                node.getpeerinfo()
                return True
            except Exception:
                sleep(1)
        return False

    def create_connections(self, connections):
        """Open every edge via addconnection using its per-edge connection type.

        Returns the list of (tank, peer, address, conn_type) tuples that were
        issued without error, for verify_connections() to confirm."""
        issued = []
        for tank, entries in connections.items():
            source = self.tanks.get(tank)
            if source is None:
                self.log.warning(f"{tank}: no such tank in this network, skipping")
                continue

            if not self._wait_rpc_ready(source, tank):
                self.log.error(
                    f"{tank}: RPC not ready after {RPC_READY_TIMEOUT}s, skipping its connections"
                )
                continue

            for entry in entries:
                peer, conn_type = self._parse_entry(entry)
                target = self.tanks.get(peer)
                if target is None:
                    self.log.warning(f"{tank}: peer {peer} not in this network, skipping")
                    continue

                address = f"{target.rpchost}:{target.p2pport}"
                try:
                    source.addconnection(address, conn_type, self.options.v2transport)
                    issued.append((tank, peer, address, conn_type))
                    self.log.info(f"{tank} --{conn_type}--> {peer} ({address})")
                except Exception as e:
                    self.log.error(f"{tank} -> {peer} ({address}) failed: {e}")

        self.log.info(f"Issued {len(issued)} addconnection calls")
        return issued

    def verify_connections(self, issued):
        """Poll getpeerinfo on each source tank until every issued connection
        appears (matched by peer address and connection type), or the timeout
        elapses. Logs an error for any that never come up.

        Tanks are polled concurrently (one thread each) so the total wait is
        bounded by CONNECT_TIMEOUT regardless of how many tanks there are."""
        # {tank: {address: conn_type}}
        expected = {}
        for tank, _, address, conn_type in issued:
            expected.setdefault(tank, {})[address] = conn_type

        # {tank: {address: conn_type}} of connections that never showed up.
        unconfirmed = {}

        def verify_tank(tank, addr_to_type):
            node = self.tanks[tank]
            pending = dict(addr_to_type)
            deadline = monotonic() + CONNECT_TIMEOUT
            while pending and monotonic() < deadline:
                try:
                    present = {
                        (peer["addr"], peer.get("connection_type")) for peer in node.getpeerinfo()
                    }
                except Exception as e:
                    self.log.warning(f"{tank}: getpeerinfo failed during verify: {e}")
                    present = set()
                for address in list(pending):
                    if (address, pending[address]) in present:
                        del pending[address]
                if pending:
                    sleep(1)
            unconfirmed[tank] = pending

        threads = [
            threading.Thread(target=verify_tank, args=(tank, addr_to_type))
            for tank, addr_to_type in expected.items()
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        confirmed = 0
        for tank, addr_to_type in expected.items():
            pending = unconfirmed.get(tank, addr_to_type)
            confirmed += len(addr_to_type) - len(pending)
            for address, conn_type in pending.items():
                self.log.error(f"{tank}: {conn_type} to {address} NOT confirmed")

        self.log.info(f"Verified {confirmed}/{len(issued)} connections via getpeerinfo")


def main():
    AddConnection("").main()


if __name__ == "__main__":
    main()
