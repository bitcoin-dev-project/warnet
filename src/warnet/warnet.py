"""
Warnet is the top-level class for a simulated network.
"""

import base64
import json
import logging
import os
import shutil
from pathlib import Path

import networkx
from backends import ComposeBackend, KubernetesBackend
from templates import TEMPLATES
from warnet.tank import Tank
from warnet.utils import gen_config_dir, load_schema, validate_graph_schema

logger = logging.getLogger("warnet")
FO_CONF_NAME = "fork_observer_config.toml"


class Warnet:
    def __init__(self, config_dir, backend, network_name: str):
        self.config_dir: Path = config_dir
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.container_interface = (
            ComposeBackend(config_dir, network_name)
            if backend == "compose"
            else KubernetesBackend(config_dir, network_name)
        )
        self.bitcoin_network: str = "regtest"
        self.network_name: str = "warnet"
        self.subnet: str = "100.0.0.0/8"
        self.graph: networkx.Graph | None = None
        self.graph_name = "graph.graphml"
        self.tanks: list[Tank] = []
        self.deployment_file: Path | None = None
        self.backend = backend
        self.node_schema = load_schema()
        self.tor = False

    def __str__(self) -> str:
        # TODO: bitcoin_conf and tc_netem can be added back in to this table
        #       if we write a helper function that can text-wrap inside a column
        template = (
            "\t" + "%-8.8s" + "%-25.24s" + "%-18.18s" + "%-18.18s" + "%-18.18s" + "%-18.18s" + "\n"
        )
        tanks_str = template % ("Index", "Version", "IPv4", "LN", "LN Image", "LN IPv4")
        for tank in self.tanks:
            tanks_str += template % (
                tank.index,
                tank.version,
                tank.ipv4,
                tank.lnnode.impl if tank.lnnode is not None else None,
                tank.lnnode.image if tank.lnnode is not None else None,
                tank.lnnode.ipv4 if tank.lnnode is not None else None,
            )
        return (
            f"Warnet:\n"
            f"\tTemp Directory: {self.config_dir}\n"
            f"\tBitcoin Network: {self.bitcoin_network}\n"
            f"\tDocker Network: {self.network_name}\n"
            f"\tSubnet: {self.subnet}\n"
            f"\tGraph: {self.graph}\n"
            f"Tanks:\n{tanks_str}"
        )

    def _warnet_dict_representation(self) -> dict:
        repr = {}
        # Warnet
        repr["warnet_headers"] = [
            "Temp dir",
            "Bitcoin network",
            "Docker network",
            "Subnet",
            "Graph",
        ]
        repr["warnet"] = [
            [
                str(self.config_dir),
                self.bitcoin_network,
                self.network_name,
                self.subnet,
                str(self.graph),
            ]
        ]

        # Tanks
        tank_headers = [
            "Index",
            "Version",
            "IPv4",
            "bitcoin conf",
            "tc_netem",
            "LN",
            "LN Image",
            "LN IPv4",
        ]
        has_ln = any(tank.lnnode and tank.lnnode.impl for tank in self.tanks)
        tanks = []
        for tank in self.tanks:
            tank_data = [tank.index, tank.version, tank.ipv4, tank.bitcoin_config, tank.netem]
            if has_ln:
                tank_data.extend(
                    [
                        tank.lnnode.impl if tank.lnnode else "",
                        tank.lnnode.image if tank.lnnode else "",
                        tank.lnnode.ipv4 if tank.lnnode else "",
                    ]
                )
            tanks.append(tank_data)
        if not has_ln:
            tank_headers.remove("LN")
            tank_headers.remove("LN IPv4")

        repr["tank_headers"] = tank_headers
        repr["tanks"] = tanks

        return repr

    @classmethod
    def from_graph_file(
        cls,
        base64_graph: str,
        config_dir: Path,
        network: str = "warnet",
        backend: str = "compose",
    ):
        self = cls(config_dir, backend, network)
        destination = self.config_dir / self.graph_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        graph_file = base64.b64decode(base64_graph)
        with open(destination, "wb") as f:
            f.write(graph_file)
        self.network_name = network
        self.graph = networkx.parse_graphml(graph_file.decode("utf-8"), node_type=int)
        validate_graph_schema(self.node_schema, self.graph)
        self.tanks_from_graph()
        if "tor" in self.graph.graph and self.graph.graph["tor"]:
            self.tor = True
        logger.info(f"Created Warnet using directory {self.config_dir}")
        return self

    @classmethod
    def from_graph(cls, graph, backend="compose", network="warnet"):
        self = cls(Path(), backend, network)
        self.graph = graph
        validate_graph_schema(self.node_schema, self.graph)
        self.tanks_from_graph()
        logger.info(f"Created Warnet using directory {self.config_dir}")
        return self

    @classmethod
    def from_network(cls, network_name, backend="compose"):
        config_dir = gen_config_dir(network_name)
        self = cls(config_dir, backend, network_name)
        self.network_name = network_name
        # Get network graph edges from graph file (required for network restarts)
        self.graph = networkx.read_graphml(Path(self.config_dir / self.graph_name), node_type=int)
        validate_graph_schema(self.node_schema, self.graph)
        self.tanks_from_graph()
        for tank in self.tanks:
            tank._ipv4 = self.container_interface.get_tank_ipv4(tank.index)
        return self

    @property
    def fork_observer_config(self):
        return self.config_dir / FO_CONF_NAME

    def tanks_from_graph(self):
        if not self.graph:
            return
        for node_id in self.graph.nodes():
            if int(node_id) != len(self.tanks):
                raise Exception(
                    f"Node ID in graph must be incrementing integers (got '{node_id}', expected '{len(self.tanks)}')"
                )
            tank = Tank.from_graph_node(node_id, self)
            # import edges as list of destinations to connect to
            for edge in self.graph.edges(data=True):
                (src, dst, data) = edge
                if "channel" in data:
                    continue
                if src == node_id:
                    tank.init_peers.append(int(dst))
            self.tanks.append(tank)
        logger.info(f"Imported {len(self.tanks)} tanks from graph")

    def apply_network_conditions(self):
        for tank in self.tanks:
            tank.apply_network_conditions()

    def warnet_build(self):
        self.container_interface.build()

    def get_ln_node_from_tank(self, index):
        return self.tanks[index].lnnode

    def warnet_up(self):
        self.container_interface.up(self)

    def warnet_down(self):
        self.container_interface.down(self)

    def generate_deployment(self):
        self.container_interface.generate_deployment_file(self)

    def write_fork_observer_config(self):
        shutil.copy(TEMPLATES / FO_CONF_NAME, self.fork_observer_config)
        with open(self.fork_observer_config, "a") as f:
            for tank in self.tanks:
                f.write(
                    f"""
                    [[networks.nodes]]
                    id = {tank.index}
                    name = "Node {tank.index}"
                    description = "Warnet tank {tank.index}"
                    rpc_host = "{tank.ipv4}"
                    rpc_port = {tank.rpc_port}
                    rpc_user = "{tank.rpc_user}"
                    rpc_password = "{tank.rpc_password}"
                """
                )
        logger.info(f"Wrote file: {self.fork_observer_config}")

    def export(self, subdir):
        if self.backend != "compose":
            raise NotImplementedError("Export is only supported for compose backend")
        config = {"nodes": []}
        for tank in self.tanks:
            tank.export(config, subdir)
        config_path = os.path.join(subdir, "sim.json")
        with open(config_path, "a") as f:
            json.dump(config, f)

    def wait_for_health(self):
        self.container_interface.wait_for_healthy_tanks(self)

    def network_connected(self):
        for tank in self.tanks:
            peerinfo = json.loads(self.container_interface.get_bitcoin_cli(tank, "getpeerinfo"))
            manuals = 0
            for peer in peerinfo:
                if peer["connection_type"] == "manual":
                    manuals += 1
            # Even if more edges are specifed, bitcoind only allows
            # 8 manual outbound connections
            if min(8, len(tank.init_peers)) > manuals:
                return False
        return True
