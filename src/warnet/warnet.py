"""
  Warnet is the top-level class for a simulated network.
"""

import base64
import json
import logging
import networkx
import os
import shutil
from pathlib import Path
from templates import TEMPLATES
from typing import List, Optional

from interfaces import DockerInterface
from warnet.tank import Tank
from warnet.utils import gen_config_dir, bubble_exception_str, version_cmp_ge

logger = logging.getLogger("warnet")
FO_CONF_NAME = "fork_observer_config.toml"


class Warnet:
    def __init__(self, config_dir):
        self.config_dir: Path = config_dir
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.container_interface = DockerInterface(config_dir)
        self.bitcoin_network: str = "regtest"
        self.network_name: str = "warnet"
        self.subnet: str = "100.0.0.0/8"
        self.graph: Optional[networkx.Graph] = None
        self.graph_name = "graph.graphml"
        self.tanks: List[Tank] = []
        self.deployment_file: Optional[Path] = None

    def __str__(self) -> str:
        # TODO: bitcoin_conf and tc_netem can be added back in to this table
        #       if we write a helper function that can text-wrap inside a column
        template =       "\t" + "%-8.8s" + "%-25.24s" + "%-18.18s" + "%-18.18s" + "%-18.18s" + "\n"
        tanks_str = template % ("Index",   "Version",   "IPv4",      "LN",        "LN IPv4")
        for tank in self.tanks:
            tanks_str += template % (
                tank.index,
                tank.version,
                tank.ipv4,
                tank.lnnode.impl if tank.lnnode is not None else None,
                tank.lnnode.ipv4 if tank.lnnode is not None else None)
        return (
            f"Warnet:\n"
            f"\tTemp Directory: {self.config_dir}\n"
            f"\tBitcoin Network: {self.bitcoin_network}\n"
            f"\tDocker Network: {self.network_name}\n"
            f"\tSubnet: {self.subnet}\n"
            f"\tGraph: {self.graph}\n"
            f"Tanks:\n{tanks_str}"
        )

    @classmethod
    @bubble_exception_str
    def from_graph_file(
        cls, base64_graph: str, config_dir: Path, network: str = "warnet"
    ):
        self = cls(config_dir)
        destination = self.config_dir / self.graph_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        graph_file = base64.b64decode(base64_graph)
        with open(destination, "wb") as f:
            f.write(graph_file)
        self.network_name = network
        self.graph = networkx.parse_graphml(graph_file.decode("utf-8"), node_type=int)
        self.tanks_from_graph()
        logger.info(f"Created Warnet using directory {self.config_dir}")
        return self

    @classmethod
    @bubble_exception_str
    def from_graph(cls, graph):
        self = cls(Path())
        self.graph = graph
        self.tanks_from_graph()
        logger.info(f"Created Warnet using directory {self.config_dir}")
        return self

    @classmethod
    @bubble_exception_str
    def from_network(cls, network_name):
        config_dir = gen_config_dir(network_name)
        self = cls(config_dir)
        self.network_name = network_name
        self.container_interface.warnet_from_deployment(self)
        # Get network graph edges from graph file (required for network restarts)
        self.graph = networkx.read_graphml(Path(self.config_dir / self.graph_name), node_type=int)
        return self

    @property
    @bubble_exception_str
    def fork_observer_config(self):
        return self.config_dir / FO_CONF_NAME

    @bubble_exception_str
    def tanks_from_graph(self):
        if not self.graph:
            return
        for node_id in self.graph.nodes():
            if int(node_id) != len(self.tanks):
                raise Exception(
                    f"Node ID in graph must be incrementing integers (got '{node_id}', expected '{len(self.tanks)}')"
                )
            self.tanks.append(Tank.from_graph_node(node_id, self))
        logger.info(f"Imported {len(self.tanks)} tanks from graph")

    @bubble_exception_str
    def apply_network_conditions(self):
        for tank in self.tanks:
            tank.apply_network_conditions()

    @bubble_exception_str
    def connect_edges(self):
        if self.graph is None:
            return

        for edge in self.graph.edges(data=True):
            (src, dst, data) = edge
            if "channel" in data:
                continue
            src_tank = self.tanks[src]
            dst_ip = self.tanks[dst].ipv4
            # <= 20.2 doesn't have addpeeraddress
            res = version_cmp_ge(src_tank.version, "0.21.0")
            if res:
                cmd = f"bitcoin-cli -regtest -rpcuser={src_tank.rpc_user} -rpcpassword={src_tank.rpc_password} addpeeraddress {dst_ip} 18444"
                logger.info(f"Using `{cmd}` to connect tanks {src} to {dst}")
            else:
                cmd = f'bitcoin-cli -regtest -rpcuser={src_tank.rpc_user} -rpcpassword={src_tank.rpc_password} addnode "{dst_ip}:18444" onetry'
                logger.info(f"Using `{cmd}` to connect tanks {src} to {dst}")
            src_tank.exec(cmd=cmd, user="bitcoin")

    @bubble_exception_str
    def warnet_build(self):
        self.container_interface.build()

    @bubble_exception_str
    def get_ln_node_from_tank(self, index):
        return self.tanks[index].lnnode

    @bubble_exception_str
    def warnet_up(self):
        self.container_interface.up()

    @bubble_exception_str
    def warnet_down(self):
        self.container_interface.down()

    def generate_deployment(self):
        self.container_interface.generate_deployment_file(self)

    @bubble_exception_str
    def write_fork_observer_config(self):
        shutil.copy(TEMPLATES / FO_CONF_NAME, self.fork_observer_config)
        with open(self.fork_observer_config, "a") as f:
            for tank in self.tanks:
                f.write(f"""
                    [[networks.nodes]]
                    id = {tank.index}
                    name = "Node {tank.index}"
                    description = "Warnet tank {tank.index}"
                    rpc_host = "{tank.ipv4}"
                    rpc_port = {tank.rpc_port}
                    rpc_user = "{tank.rpc_user}"
                    rpc_password = "{tank.rpc_password}"
                """)
        logger.info(f"Wrote file: {self.fork_observer_config}")


    @bubble_exception_str
    def export(self, subdir):
        config = {"nodes": []}
        for tank in self.tanks:
            tank.export(config, subdir)
        config_path = os.path.join(subdir, "sim.json")
        with open(config_path, "a") as f:
            json.dump(config, f)

