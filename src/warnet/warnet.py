"""
  Warnet is the top-level class for a simulated network.
"""

import logging
import networkx
import shutil
import yaml
from pathlib import Path
from templates import TEMPLATES
from typing import List, Optional

from services.prometheus import Prometheus
from services.node_exporter import NodeExporter
from services.grafana import Grafana
from interfaces import DockerInterface
from warnet.tank import Tank
from warnet.utils import bubble_exception_str, version_cmp_ge

logger = logging.getLogger("warnet")
FO_CONF_NAME = "fork_observer_config.toml"


class Warnet:
    def __init__(self, config_dir, network_name = "warnet"):
        self.config_dir: Path = config_dir
        self.network_name = network_name
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.container_interface = DockerInterface(self.network_name, config_dir)
        self.bitcoin_network: str = "regtest"
        self.subnet: str = "100.0.0.0/8"
        self.graph: Optional[networkx.Graph] = None
        self.graph_name = "graph.graphml"
        self.tanks: List[Tank] = []
        self.deployment_file: Optional[Path] = None

    def __str__(self) -> str:
        template = "\t%-8.8s%-25.24s%-25.24s%-25.24s%-18.18s\n"
        tanks_str = template % ("Index", "Version", "Conf", "Netem", "IPv4")
        for tank in self.tanks:
            tanks_str += template % (tank.index, tank.version, tank.conf, tank.netem, tank.ipv4)
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
        cls, graph_file: str, config_dir: Path, network: str = "warnet"
    ):
        self = cls(config_dir, network)
        destination = self.config_dir / self.graph_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(graph_file, destination)
        self.network_name = network
        self.graph = networkx.read_graphml(graph_file, node_type=int)
        self.tanks_from_graph()
        logger.info(f"Created Warnet using directory {self.config_dir}")
        return self

    @classmethod
    @bubble_exception_str
    def from_graph(cls, graph, network: str = "warnet"):
        self = cls(Path(), network)
        self.graph = graph
        self.tanks_from_graph()
        logger.info(f"Created Warnet using directory {self.config_dir}")
        return self

    @classmethod
    @bubble_exception_str
    def from_network(cls, basedir, network_name):
        config_dir = basedir / network_name
        self = cls(config_dir, network_name)
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

        for edge in self.graph.edges():
            (src, dst) = edge
            src_tank = self.tanks[src]
            dst_ip = self.tanks[dst].ipv4
            # <= 20.2 doesn't have addpeeraddress
            res = version_cmp_ge(src_tank.version, "0.21.0")
            if res:
                logger.info(f"Using `addpeeraddress` to connect tanks {src} to {dst}")
                cmd = f"bitcoin-cli addpeeraddress {dst_ip} 18444"
            else:
                logger.info(f"Using `addnode` to connect tanks {src} to {dst}")
                cmd = f'bitcoin-cli addnode "{dst_ip}:18444" onetry'
            src_tank.exec(cmd=cmd, user="bitcoin")

    @bubble_exception_str
    def warnet_build(self):
        self.container_interface.build()

    @bubble_exception_str
    def warnet_up(self):
        self.container_interface.up()

    @bubble_exception_str
    def warnet_down(self):
        self.container_interface.down()

    def generate_deployment(self):
        self.container_interface.generate_deployment_file(self)

    @bubble_exception_str
    def write_prometheus_config(self):
        config = {
            "global": {"scrape_interval": "15s"},
            "scrape_configs": [
                {
                    "job_name": "prometheus",
                    "scrape_interval": "5s",
                    "static_configs": [{"targets": ["localhost:9090"]}],
                },
                {
                    "job_name": "node-exporter",
                    "scrape_interval": "5s",
                    "static_configs": [{"targets": ["node-exporter:9100"]}],
                },
                {
                    "job_name": "cadvisor",
                    "scrape_interval": "5s",
                    "static_configs": [{"targets": ["cadvisor:8080"]}],
                },
            ],
        }

        # grep: disable-exporters
        # for tank in self.tanks:
        #     tank.add_scrapers(config["scrape_configs"])
        #
        # prometheus_path = self.config_dir / "prometheus.yml"
        # try:
        #     with open(prometheus_path, "w") as file:
        #         yaml.dump(config, file)
        #     logger.info(f"Wrote file: {prometheus_path}")
        # except Exception as e:
        #     logger.error(f"An error occurred while writing to {prometheus_path}: {e}")


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

