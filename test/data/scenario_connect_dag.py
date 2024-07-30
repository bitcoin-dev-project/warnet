#!/usr/bin/env python3

import os
from enum import Enum, auto, unique
from time import sleep

from warnet.test_framework_bridge import WarnetTestFramework


def cli_help():
    return "Connect a complete DAG from a set of unconnected nodes"


@unique
class ConnectionType(Enum):
    IP = auto()
    DNS = auto()


class ConnectDag(WarnetTestFramework):
    def set_test_params(self):
        # This is just a minimum
        self.num_nodes = 10

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
        eight_peers = self.nodes[8].getpeerinfo()
        nine_peers = self.nodes[9].getpeerinfo()

        for tank in self.warnet.tanks:
            self.log.info(
                f"Tank {tank.index}: {tank.warnet.tanks[tank.index].get_dns_addr()} pod:"
                f" {tank.warnet.tanks[tank.index].get_ip_addr()}"
            )

        self.assert_connection(zero_peers, 2, ConnectionType.DNS)
        self.assert_connection(one_peers, 2, ConnectionType.DNS)
        self.assert_connection(one_peers, 3, ConnectionType.DNS)
        self.assert_connection(two_peers, 0, ConnectionType.IP)
        self.assert_connection(two_peers, 1, ConnectionType.IP)
        self.assert_connection(two_peers, 3, ConnectionType.DNS)
        self.assert_connection(two_peers, 4, ConnectionType.DNS)
        self.assert_connection(three_peers, 1, ConnectionType.IP)
        self.assert_connection(three_peers, 2, ConnectionType.IP)
        self.assert_connection(three_peers, 5, ConnectionType.DNS)
        self.assert_connection(four_peers, 2, ConnectionType.IP)
        self.assert_connection(four_peers, 5, ConnectionType.IP)
        self.assert_connection(five_peers, 3, ConnectionType.IP)
        self.assert_connection(five_peers, 4, ConnectionType.DNS)
        self.assert_connection(five_peers, 6, ConnectionType.DNS)
        self.assert_connection(six_peers, 5, ConnectionType.IP)
        self.assert_connection(six_peers, 7, ConnectionType.DNS)
        self.assert_connection(seven_peers, 6, ConnectionType.IP)
        # Check the pre-connected nodes
        self.assert_connection(eight_peers, 9, ConnectionType.DNS)
        self.assert_connection(nine_peers, 8, ConnectionType.IP)

        self.log.info(
            f"Successfully ran the connect_dag.py scenario using a temporary file: "
            f"{os.path.basename(__file__)} "
        )

    def assert_connection(self, connector, connectee_index, connection_type: ConnectionType):
        if connection_type == ConnectionType.DNS:
            assert any(
                d.get("addr") == self.warnet.tanks[connectee_index].get_dns_addr()
                for d in connector
            ), f"Could not find {self.options.network_name}-tank-00000{connectee_index}-service"
        elif connection_type == ConnectionType.IP:
            assert any(
                d.get("addr").split(":")[0] == self.warnet.tanks[connectee_index].get_ip_addr()
                for d in connector
            ), f"Could not find Tank {connectee_index}'s ip addr"
        else:
            raise ValueError("ConnectionType must be of type DNS or IP")


if __name__ == "__main__":
    ConnectDag().main()
