#!/usr/bin/env python3

import os
from time import sleep

from warnet.test_framework_bridge import WarnetTestFramework


def cli_help():
    return "Connect a complete DAG from a set of unconnected nodes"


class ConnectDag(WarnetTestFramework):
    def set_test_params(self):
        # This is just a minimum
        self.num_nodes = 8

    def add_options(self, parser):
        parser.add_argument(
            "--network_name",
            dest="network_name",
            default="warnet",
            help="",
        )

    def run_test(self):
        while not self.warnet.network_connected():
            sleep(1)

        # All permutations of a directed acyclic graph with zero, one, or two inputs/outputs
        #
        # │ Node │ In │ Out │ Con In │ Con Out │
        # ├──────┼────┼─────┼────────┼─────────┤
        # │  A   │  0 │   1 │ ─      │ C       │
        # │  B   │  0 │   2 │ ─      │ C, D    │
        # │  C   │  2 │   2 │ A, B   │ D, E    │
        # │  D   │  2 │   1 │ B, C   │ F       │
        # │  E   │  2 │   0 │ C, F   │ ─       │
        # │  F   │  1 │   2 │ D      │ E, G    │
        # │  G   │  1 │   1 │ F      │ H       │
        # │  H   │  1 │   0 │ G      │ ─       │
        #
        #           Node Graph                 Corresponding Indices
        #  ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈    ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈
        #          ╭──────> E                      ╭──────> 4
        #          │        ∧                      │        ∧
        #  A ─> C ─┤        │              0 ─> 2 ─┤        │
        #       ∧  ╰─> D ─> F ─> G ─> H         ∧  ╰─> 3 ─> 5 ─> 6 ─> 7
        #       │      ∧                        │      ∧
        #  B ───┴──────╯                   1 ───┴──────╯

        self.connect_nodes(0, 2)
        self.connect_nodes(1, 2)
        self.connect_nodes(1, 3)
        self.connect_nodes(2, 3)
        self.connect_nodes(2, 4)
        self.connect_nodes(3, 5)
        self.connect_nodes(5, 4)
        self.connect_nodes(5, 6)
        self.connect_nodes(6, 7)

        # Nodes 8 & 9 shall come pre-connected. Attempt to connect them anyway to test the handling
        # of dns node addresses
        self.connect_nodes(8, 9)
        self.connect_nodes(9, 8)

        self.sync_all()

        zero_peers = self.nodes[0].getpeerinfo()
        one_peers = self.nodes[1].getpeerinfo()
        two_peers = self.nodes[2].getpeerinfo()
        three_peers = self.nodes[3].getpeerinfo()
        four_peers = self.nodes[4].getpeerinfo()
        five_peers = self.nodes[5].getpeerinfo()
        six_peers = self.nodes[6].getpeerinfo()
        seven_peers = self.nodes[7].getpeerinfo()

        for tank in self.warnet.tanks:
            self.log.info(f"Tank {tank.index}: {tank.warnet.tanks[tank.index].get_dns_addr()} pod:"
                          f" {tank.warnet.tanks[tank.index].get_ip_addr()}")

        assert any(d.get("addr").split(":")[0] == self.warnet.tanks[2].get_dns_addr() for d in
                   zero_peers), f"Could not find {self.options.network_name}-tank-000002-service"
        assert any(d.get("addr").split(":")[0] == self.warnet.tanks[2].get_dns_addr() for d in
                   one_peers), f"Could not find {self.options.network_name}-tank-000002-service"
        assert any(d.get("addr").split(":")[0] == self.warnet.tanks[3].get_dns_addr() for d in
                   one_peers), f"Could not find {self.options.network_name}-tank-000003-service"
        assert any(d.get("addr").split(":")[0] == self.warnet.tanks[0].get_ip_addr() for d in
                   two_peers), f"Could not find Tank 0's ip addr"
        assert any(d.get("addr").split(":")[0] == self.warnet.tanks[1].get_ip_addr() for d in
                   two_peers), f"Could not find Tank 1's ip addr"
        assert any(d.get("addr").split(":")[0] == self.warnet.tanks[3].get_dns_addr() for d in
                   two_peers), f"Could not find {self.options.network_name}-tank-000003-service"
        assert any(d.get("addr").split(":")[0] == self.warnet.tanks[4].get_dns_addr() for d in
                   two_peers), f"Could not find {self.options.network_name}-tank-000004-service"
        assert any(d.get("addr").split(":")[0] == self.warnet.tanks[1].get_ip_addr() for d in
                   three_peers), f"Could not find Tank 1's ip addr"
        assert any(d.get("addr").split(":")[0] == self.warnet.tanks[2].get_ip_addr() for d in
                   three_peers), f"Could not find Tank 2's ip addr"
        assert any(d.get("addr").split(":")[0] == self.warnet.tanks[5].get_dns_addr() for d in
                   three_peers), f"Could not find {self.options.network_name}-tank-000005-service"
        assert any(d.get("addr").split(":")[0] == self.warnet.tanks[2].get_ip_addr() for d in
                   four_peers), f"Could not find Tank 2's ip addr"
        assert any(d.get("addr").split(":")[0] == self.warnet.tanks[5].get_ip_addr() for d in
                   four_peers), f"Could not find Tank 5's ip addr"
        assert any(d.get("addr").split(":")[0] == self.warnet.tanks[3].get_ip_addr() for d in
                   five_peers), f"Could not find Tank 3's ip addr"
        assert any(d.get("addr").split(":")[0] == self.warnet.tanks[4].get_dns_addr() for d in
                   five_peers), f"Could not find {self.options.network_name}-tank-000004-service"
        assert any(d.get("addr").split(":")[0] == self.warnet.tanks[6].get_dns_addr() for d in
                   five_peers), f"Could not find {self.options.network_name}-tank-000006-service"
        assert any(d.get("addr").split(":")[0] == self.warnet.tanks[5].get_ip_addr() for d in
                   six_peers), f"Could not find Tank 5's ip addr"
        assert any(d.get("addr").split(":")[0] == self.warnet.tanks[7].get_dns_addr() for d in
                   six_peers), f"Could not find {self.options.network_name}-tank-000007-service"
        assert any(d.get("addr").split(":")[0] == self.warnet.tanks[6].get_ip_addr() for d in
                   seven_peers), f"Could not find Tank 6's ip addr"

        self.log.info(f"Successfully ran the {os.path.basename(__file__)} scenario.")


if __name__ == "__main__":
    ConnectDag().main()
