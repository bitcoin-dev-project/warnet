#!/usr/bin/env python3

import threading
from time import sleep

from commander import Commander

DEFAULT_CONNECTION_TYPE = "outbound-full-relay"
DEFAULT_TRANSPORT_PROTOCOL_TYPE = "v2"


class AddConnectionInit(Commander):
    def set_test_params(self):
        self.num_nodes = None

    def add_options(self, parser):
        parser.description = "Connect tanks with specific connection types after deployment"
        parser.usage = "warnet run /path/to/addconnection_init.py"

    def run_test(self):
        self.log.info("Waiting for RPC availability and addnode connections...")
        self.wait_for_tanks_connected()

        self.log.info("Connecting addconnection tanks...")

        def addconnection(self, node, peer, conn_type, v2):
            while True:
                try:
                    result = node.addconnection(peer, conn_type, v2)
                    self.log.info(f"Connected {node.tank} to {peer}: {result}")
                    break
                except Exception as e:
                    self.log.info(
                        f"Couldn't connect {node.tank} to {peer}: {e}, retrying in 5 seconds..."
                    )
                    sleep(5)

        conn_threads = []

        for node in self.nodes:
            for connection in node.addconnection_peers:
                self.log.info(f"Connecting {node.tank} {connection}")
                conn_threads.append(
                    threading.Thread(
                        target=addconnection,
                        args=(
                            self,
                            node,
                            connection["to"],
                            connection.get("type", DEFAULT_CONNECTION_TYPE),
                            connection.get("v2", DEFAULT_TRANSPORT_PROTOCOL_TYPE == "v2"),
                        ),
                    )
                )

        for thread in conn_threads:
            thread.start()

        all(thread.join() is None for thread in conn_threads)
        self.log.info("All addconnection commands executed, waiting for confirmation...")

        def check_addconnections(self, node):
            expected = node.addconnection_peers
            if not expected:
                return
            poll = True
            while poll:
                actual = node.getpeerinfo()
                for expected_connection in expected:
                    if any(
                        actual_connection["addr"] == expected_connection["to"]
                        and actual_connection["connection_type"]
                        == (expected_connection.get("type", DEFAULT_CONNECTION_TYPE))
                        and actual_connection["transport_protocol_type"]
                        == (
                            "v1"
                            if "v2" in expected_connection and not expected_connection["v2"]
                            else DEFAULT_TRANSPORT_PROTOCOL_TYPE
                        )
                        for actual_connection in actual
                    ):
                        self.log.info(f"Connection complete: {node.tank} {expected_connection}")
                        poll = False
                    else:
                        self.log.info(
                            f"Connection incomplete: {node.tank} {expected_connection}, retrying in 5 seconds..."
                        )
                        sleep(5)
                        poll = True
                        break

        check_threads = [
            threading.Thread(target=check_addconnections, args=(self, node)) for node in self.nodes
        ]
        for thread in check_threads:
            thread.start()

        all(thread.join() is None for thread in check_threads)
        self.log.info("All addconnection connections are complete")


def main():
    AddConnectionInit("").main()


if __name__ == "__main__":
    main()
