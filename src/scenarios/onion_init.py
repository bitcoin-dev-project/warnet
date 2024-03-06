#!/usr/bin/env python3

from time import sleep

from warnet.test_framework_bridge import WarnetTestFramework


def cli_help():
    return "Connect tanks over internal Tor network"


class OnionInit(WarnetTestFramework):
    def set_test_params(self):
        self.num_nodes = 12

    def run_test(self):
        ready = False
        while not ready:
            sleep(10)
            self.log.info("Waiting for Tor DA health")
            ready = self.warnet.container_interface.tor_ready()

        for tank in self.warnet.tanks:
            info = self.nodes[tank.index].getnetworkinfo()
            for addr in info["localaddresses"]:
                if "onion" in addr["address"]:
                    dst = tank.index
                    src = (tank.index + 1) % len(self.warnet.tanks)
                    self.log.info(f"connecting from {src} to {dst} at {addr['address']}:{addr['port']}")
                    self.nodes[src].addpeeraddress(addr['address'], addr['port'])
                    continue

if __name__ == "__main__":
    OnionInit().main()
