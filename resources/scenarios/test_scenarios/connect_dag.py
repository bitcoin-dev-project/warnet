#!/usr/bin/env python3

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
        self.num_nodes = 1

    def add_options(self, parser):
        parser.description = "Connect some nodes"
        parser.usage = "warnet run /path/to/scenario_connect_dag.py"

    def run_test(self):
        self.connect_nodes(0, 2)
        self.connect_nodes(1, 2)
        self.connect_nodes(1, 3)

        self.sync_all()

        tank0_peers = self.tanks["tank-0000"].getpeerinfo()
        tank1_peers = self.tanks["tank-0001"].getpeerinfo()
        tank2_peers = self.tanks["tank-0002"].getpeerinfo()
        tank3_peers = self.tanks["tank-0003"].getpeerinfo()
        tank8_peers = self.tanks["tank-0008"].getpeerinfo()
        tank9_peers = self.tanks["tank-0009"].getpeerinfo()

        for node in self.nodes:
            self.log.info(f"Node {node.index}: tank={node.tank} ip={node.rpchost}")

        # Check the manual connect_nodes() connections
        self.assert_connection(tank0_peers, 2, ConnectionType.IP)
        self.assert_connection(tank1_peers, 2, ConnectionType.IP)
        self.assert_connection(tank1_peers, 3, ConnectionType.IP)

        # Ensure the other end of the connection agrees
        self.assert_connection(tank2_peers, 0, ConnectionType.IP)
        self.assert_connection(tank2_peers, 1, ConnectionType.IP)
        self.assert_connection(tank3_peers, 1, ConnectionType.IP)

        # Check the pre-connected nodes
        # The only connection made by DNS name would be from the initial graph edges
        self.assert_connection(tank8_peers, 9, ConnectionType.DNS)
        self.assert_connection(tank9_peers, 8, ConnectionType.IP)

    def assert_connection(self, connector, connectee_index, connection_type: ConnectionType):
        if connection_type == ConnectionType.DNS:
            assert any(
                # ignore the ...-service suffix
                self.nodes[connectee_index].tank in (d.get("addr") or "")
                for d in connector
            ), "Could not find connectee hostname"
        elif connection_type == ConnectionType.IP:
            assert any(
                (d.get("addr") or "").split(":")[0] == self.nodes[connectee_index].rpchost
                for d in connector
            ), "Could not find connectee ip addr"
        else:
            raise ValueError("ConnectionType must be of type DNS or IP")


def main():
    ConnectDag("").main()


if __name__ == "__main__":
    main()
