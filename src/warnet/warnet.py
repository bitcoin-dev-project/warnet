"""
Warnet is the top-level class for a simulated network.
"""

import base64
import json
import logging
import shutil
from pathlib import Path

import networkx
import yaml

from .backend.kubernetes_backend import KubernetesBackend
from .services import AO_CONF_NAME, FO_CONF_NAME, GRAFANA_PROVISIONING, PROM_CONF_NAME
from .tank import Tank
from .templates import TEMPLATES
from .utils import gen_config_dir, load_schema, validate_graph_schema

logger = logging.getLogger("warnet")


class Warnet:
    def __init__(self, config_dir, network_name: str):
        self.config_dir: Path = config_dir
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.container_interface = KubernetesBackend(config_dir, network_name)
        self.bitcoin_network: str = "regtest"
        self.network_name: str = "warnet"
        self.subnet: str = "100.0.0.0/8"
        self.graph: networkx.Graph | None = None
        self.graph_name = "graph.graphml"
        self.tanks: list[Tank] = []
        self.deployment_file: Path | None = None
        self.graph_schema = load_schema()
        self.services = []

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
            tank_data = [
                tank.index,
                tank.version if tank.version else tank.image,
                tank.ipv4,
                tank.bitcoin_config,
                tank.netem,
            ]
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
    ):
        self = cls(config_dir, network)
        destination = self.config_dir / self.graph_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        graph_file = base64.b64decode(base64_graph)
        with open(destination, "wb") as f:
            f.write(graph_file)
        self.network_name = network
        self.graph = networkx.parse_graphml(
            graph_file.decode("utf-8"), node_type=int, force_multigraph=True
        )
        validate_graph_schema(self.graph)
        self.tanks_from_graph()
        if "services" in self.graph.graph:
            self.services = self.graph.graph["services"].split()
        logger.info(f"Created Warnet using directory {self.config_dir}")
        return self

    @classmethod
    def from_graph(cls, graph, network="warnet"):
        self = cls(Path(), network)
        self.graph = graph
        validate_graph_schema(self.graph)
        self.tanks_from_graph()
        if "services" in self.graph.graph:
            self.services = self.graph.graph["services"].split()
        logger.info(f"Created Warnet using directory {self.config_dir}")
        return self

    @classmethod
    def from_network(cls, network_name):
        config_dir = gen_config_dir(network_name)
        self = cls(config_dir, network_name)
        self.network_name = network_name
        # Get network graph edges from graph file (required for network restarts)
        self.graph = networkx.read_graphml(
            Path(self.config_dir / self.graph_name), node_type=int, force_multigraph=True
        )
        validate_graph_schema(self.graph)
        self.tanks_from_graph()
        if "services" in self.graph.graph:
            self.services = self.graph.graph["services"].split()
        for tank in self.tanks:
            tank._ipv4 = self.container_interface.get_tank_ipv4(tank.index)
        return self

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
                # Ignore LN edges for now
                if "channel_open" in data:
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
        if "forkobserver" in self.services:
            self.write_fork_observer_config()
        if "addrmanobserver" in self.services:
            self.write_addrman_observer_config()
        if "grafana" in self.services:
            self.write_grafana_config()
        if "prometheus" in self.services:
            self.write_prometheus_config()

    def write_fork_observer_config(self):
        src = TEMPLATES / FO_CONF_NAME
        dst = self.config_dir / FO_CONF_NAME
        shutil.copy(src, dst)
        with open(dst, "a") as f:
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
        logger.info(f"Wrote file: {dst}")

    def write_addrman_observer_config(self):
        src = TEMPLATES / AO_CONF_NAME
        dst = self.config_dir / AO_CONF_NAME
        shutil.copy(src, dst)
        with open(dst, "a") as f:
            for tank in self.tanks:
                f.write(
                    f"""
                    [[nodes]]
                    id = {tank.index}
                    name = "node-{tank.index}"
                    rpc_host = "{tank.ipv4}"
                    rpc_port = {tank.rpc_port}
                    rpc_user = "{tank.rpc_user}"
                    rpc_password = "{tank.rpc_password}"
                """
                )
        logger.info(f"Wrote file: {dst}")

    def write_grafana_config(self):
        src = TEMPLATES / GRAFANA_PROVISIONING
        dst = self.config_dir / GRAFANA_PROVISIONING
        shutil.copytree(src, dst, dirs_exist_ok=True)
        logger.info(f"Wrote directory: {dst}")

    def write_prometheus_config(self):
        scrape_configs = [
            {
                "job_name": "cadvisor",
                "scrape_interval": "15s",
                "static_configs": [{"targets": [f"{self.network_name}_cadvisor:8080"]}],
            }
        ]
        for tank in self.tanks:
            if tank.exporter:
                scrape_configs.append(
                    {
                        "job_name": tank.exporter_name,
                        "scrape_interval": "5s",
                        "static_configs": [{"targets": [f"{tank.exporter_name}:9332"]}],
                    }
                )
        config = {"global": {"scrape_interval": "15s"}, "scrape_configs": scrape_configs}
        prometheus_path = self.config_dir / PROM_CONF_NAME
        try:
            with open(prometheus_path, "w") as file:
                yaml.dump(config, file)
            logger.info(f"Wrote file: {prometheus_path}")
        except Exception as e:
            logger.error(f"An error occurred while writing to {prometheus_path}: {e}")

    def export(self, config: object, tar_file, exclude: list[int]):
        for tank in self.tanks:
            if tank.index not in exclude:
                tank.export(config, tar_file)

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
