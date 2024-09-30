#!/usr/bin/env python3

import os
from enum import Enum, auto, unique

# The base class exists inside the commander container
from commander import Commander


@unique
class ConnectionType(Enum):
    IP = auto()
    DNS = auto()


class ConnectDag(Commander):
    def set_test_params(self):
        # This is just a minimum
        self.num_nodes = 10

    def add_options(self, parser):
        parser.description = "Connect a complete DAG from a set of unconnected nodes"
        parser.usage = "warnet run /path/to/scenario_connect_dag.py"

    def run_test(self):
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
        self.sync_all()

        zero_peers = self.tanks["tank-0000"].getpeerinfo()
        one_peers = self.tanks["tank-0001"].getpeerinfo()
        two_peers = self.tanks["tank-0002"].getpeerinfo()
        three_peers = self.tanks["tank-0003"].getpeerinfo()
        four_peers = self.tanks["tank-0004"].getpeerinfo()
        five_peers = self.tanks["tank-0005"].getpeerinfo()
        six_peers = self.tanks["tank-0006"].getpeerinfo()
        seven_peers = self.tanks["tank-0007"].getpeerinfo()
        eight_peers = self.tanks["tank-0008"].getpeerinfo()
        nine_peers = self.tanks["tank-0009"].getpeerinfo()

        for node in self.nodes:
            self.log.info(f"Node {node.index}: tank={node.tank} ip={node.rpchost}")

        self.assert_connection(zero_peers, 2, ConnectionType.IP)
        self.assert_connection(one_peers, 2, ConnectionType.IP)
        self.assert_connection(one_peers, 3, ConnectionType.IP)
        self.assert_connection(two_peers, 0, ConnectionType.IP)
        self.assert_connection(two_peers, 1, ConnectionType.IP)
        self.assert_connection(two_peers, 3, ConnectionType.IP)
        self.assert_connection(two_peers, 4, ConnectionType.IP)
        self.assert_connection(three_peers, 1, ConnectionType.IP)
        self.assert_connection(three_peers, 2, ConnectionType.IP)
        self.assert_connection(three_peers, 5, ConnectionType.IP)
        self.assert_connection(four_peers, 2, ConnectionType.IP)
        self.assert_connection(four_peers, 5, ConnectionType.IP)
        self.assert_connection(five_peers, 3, ConnectionType.IP)
        self.assert_connection(five_peers, 4, ConnectionType.IP)
        self.assert_connection(five_peers, 6, ConnectionType.IP)
        self.assert_connection(six_peers, 5, ConnectionType.IP)
        self.assert_connection(six_peers, 7, ConnectionType.IP)
        self.assert_connection(seven_peers, 6, ConnectionType.IP)
        # Check the pre-connected nodes
        # The only connection made by DNS name would be from the initial graph edges
        self.assert_connection(eight_peers, 9, ConnectionType.DNS)
        self.assert_connection(nine_peers, 8, ConnectionType.IP)

        # TODO: This needs to cause the test to fail
        # assert False

        self.log.info(
            f"Successfully ran the connect_dag.py scenario using a temporary file: "
            f"{os.path.basename(__file__)} "
        )

    def assert_connection(self, connector, connectee_index, connection_type: ConnectionType):
        if connection_type == ConnectionType.DNS:
            assert any(
                # ignore the ...-service suffix
                self.nodes[connectee_index].tank in d.get("addr")
                for d in connector
            ), "Could not find conectee hostname"
        elif connection_type == ConnectionType.IP:
            assert any(
                d.get("addr").split(":")[0] == self.nodes[connectee_index].rpchost
                for d in connector
            ), "Could not find connectee ip addr"
        else:
            raise ValueError("ConnectionType must be of type DNS or IP")


def main():
    ConnectDag().main()


if __name__ == "__main__":
    main()
