#!/usr/bin/env python3

import threading
from time import sleep

from commander import Commander


class AddConnectionInit(Commander):
    def set_test_params(self):
        self.num_nodes = None

    def add_options(self, parser):
        parser.description = "Connect tanks with specific connection types after deployment"
        parser.usage = "warnet run /path/to/addconnection_init.py"

    def run_test(self):
        self.log.info("Connecting tanks...")

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
                            connection.get("type", "outbound-full-relay"),
                            connection.get("v2", True),
                        ),
                    )
                )

        for thread in conn_threads:
            thread.start()

        all(thread.join() is None for thread in conn_threads)
        self.log.info("Post-deploy connections are complete!")


def main():
    AddConnectionInit("").main()


if __name__ == "__main__":
    main()
