"""
  Warnet is the top-level class for a simulated network.
"""

import docker
import logging
import networkx
import shutil
import subprocess
import yaml
from pathlib import Path
from templates import TEMPLATES
from typing import List

from services.prometheus import Prometheus
from services.node_exporter import NodeExporter
from services.grafana import Grafana
from services.tor import Tor
from services.fork_observer import ForkObserver
# from services.fluentd import FLUENT_CONF, Fluentd, FLUENT_IP
from services.dns_seed import DnsSeed, ZONE_FILE_NAME, DNS_SEED_NAME
from warnet.tank import Tank
from warnet.utils import parse_bitcoin_conf, gen_config_dir, bubble_exception_str, version_cmp_ge

logger = logging.getLogger("warnet")
FO_CONF_NAME = "fork_observer_config.toml"
logging.getLogger("docker.utils.config").setLevel(logging.WARNING)
logging.getLogger("docker.auth").setLevel(logging.WARNING)


class Warnet:
    def __init__(self, config_dir):
        self.config_dir: Path = config_dir
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.docker = docker.from_env()
        self.bitcoin_network: str = "regtest"
        self.docker_network: str = "warnet"
        self.subnet: str = "100.0.0.0/8"
        self.graph = None
        self.graph_name = "graph.graphml"
        self.tanks: List[Tank] = []


    def __str__(self) -> str:
        template = "\t%-8.8s%-25.24s%-25.24s%-25.24s%-18.18s\n"
        tanks_str = template % ("Index", "Version", "Conf", "Netem", "IPv4")
        for tank in self.tanks:
            tanks_str += template % (tank.index, tank.version, tank.conf, tank.netem, tank.ipv4)
        return (
            f"Warnet:\n"
            f"\tTemp Directory: {self.config_dir}\n"
            f"\tBitcoin Network: {self.bitcoin_network}\n"
            f"\tDocker Network: {self.docker_network}\n"
            f"\tSubnet: {self.subnet}\n"
            f"\tGraph: {self.graph}\n"
            f"Tanks:\n{tanks_str}"
        )

    @classmethod
    @bubble_exception_str
    def from_graph_file(
        cls, graph_file: str, config_dir: Path, network: str = "warnet"
    ):
        self = cls(config_dir)
        destination = self.config_dir / self.graph_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(graph_file, destination)
        self.docker_network = network
        self.graph = networkx.read_graphml(graph_file, node_type=int)
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
        self.docker_network = network_name

        # Get tank names, versions and IP addresses from docker-compose
        docker_compose_path = self.config_dir / "docker-compose.yml"
        compose = None
        with open(docker_compose_path, "r") as file:
            compose = yaml.safe_load(file)
        for service_name in compose["services"]:
            tank = Tank.from_docker_compose_service(compose["services"][service_name], network_name)
            if tank is not None:
                self.tanks.append(tank)

        # Get network graph edges from graph file (required for network restarts)
        self.graph = networkx.read_graphml(Path(self.config_dir / self.graph_name), node_type=int)

        return self

    @property
    @bubble_exception_str
    def zone_file_path(self):
        return self.config_dir / ZONE_FILE_NAME

    @property
    @bubble_exception_str
    def fork_observer_config(self):
        return self.config_dir / FO_CONF_NAME

    @bubble_exception_str
    def tanks_from_graph(self):
        for node_id in self.graph.nodes():
            if int(node_id) != len(self.tanks):
                raise Exception(
                    f"Node ID in graph must be incrementing integers (got '{node_id}', expected '{len(self.tanks)}')"
                )
            self.tanks.append(Tank.from_graph_node(node_id, self))
        logger.info(f"Imported {len(self.tanks)} tanks from graph")

    @bubble_exception_str
    def write_bitcoin_confs(self):
        with open(TEMPLATES / "bitcoin.conf", "r") as file:
            text = file.read()
        base_bitcoin_conf = parse_bitcoin_conf(text)
        for tank in self.tanks:
            tank.write_bitcoin_conf(base_bitcoin_conf)

    @bubble_exception_str
    def apply_network_conditions(self):
        for tank in self.tanks:
            tank.apply_network_conditions()

    @bubble_exception_str
    def generate_zone_file_from_tanks(self):
        records_list = [
            f"x9.dummySeed.invalid.     300 IN  A   {tank.ipv4}" for tank in self.tanks
        ]
        content = []
        with open(str(TEMPLATES / ZONE_FILE_NAME), "r") as f:
            content = [line.rstrip() for line in f]

        # TODO: Really we should also read active SOA value from dns-seed, and increment from there

        content.extend(records_list)
        # Join the content into a single string and escape single quotes for echoing
        content_str = "\n".join(content).replace("'", "'\\''")
        with open(self.config_dir / ZONE_FILE_NAME, "w") as f:
            f.write(content_str)

    @bubble_exception_str
    def apply_zone_file(self):
        """
        Sync the dns seed list served by dns-seed with currently active Tanks.
        """
        seeder = self.docker.containers.get(f"{self.docker_network}_{DNS_SEED_NAME}")

        # Read the content from the generated zone file
        with open(self.config_dir / ZONE_FILE_NAME, "r") as f:
            content_str = f.read().replace("'", "'\\''")

        # Overwrite all existing content
        result = seeder.exec_run(
            f"sh -c 'echo \"{content_str}\" > /etc/bind/invalid.zone'"
        )
        logger.debug(f"result of updating {ZONE_FILE_NAME}: {result}")

        # Reload that single zone only
        seeder.exec_run("rndc reload invalid")

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
    def docker_compose_build_up(self):
        command = ["docker-compose", "-p", self.docker_network, "up", "-d", "--build"]
        try:
            with subprocess.Popen(
                command,
                cwd=str(self.config_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            ) as process:
                for line in process.stdout:
                    logger.info(line.decode().rstrip())
        except Exception as e:
            logger.error(
                f"An error occurred while executing `{' '.join(command)}` in {self.config_dir}: {e}"
            )

    @bubble_exception_str
    def docker_compose_up(self):
        command = ["docker-compose", "-p", self.docker_network, "up", "-d"]
        try:
            with subprocess.Popen(
                command,
                cwd=str(self.config_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            ) as process:
                for line in process.stdout:
                    logger.info(line.decode().rstrip())
        except Exception as e:
            logger.error(
                f"An error occurred while executing `{' '.join(command)}` in {self.config_dir}: {e}"
            )

    @bubble_exception_str
    def docker_compose_down(self):
        command = ["docker-compose", "down"]
        try:
            with subprocess.Popen(
                command,
                cwd=str(self.config_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            ) as process:
                for line in process.stdout:
                    logger.info(line.decode().rstrip())
        except Exception as e:
            logger.error(
                f"An error occurred while executing `{' '.join(command)}` in {self.config_dir}: {e}"
            )

    @bubble_exception_str
    def write_docker_compose(self, dns=True):
        compose = {
            "version": "3.8",
            "networks": {
                self.docker_network: {
                    "name": self.docker_network,
                    "ipam": {"config": [{"subnet": self.subnet}]},
                }
            },
            "volumes": {"grafana-storage": None},
            "services": {},
        }

        # Pass services object to each tank so they can add whatever they need.
        for tank in self.tanks:
            tank.add_services(compose["services"])

        # Initialize services and add them to the compose
        services = [
            # grep: disable-exporters
            # Prometheus(self.docker_network, self.config_dir),
            # NodeExporter(self.docker_network),
            # Grafana(self.docker_network),
            Tor(self.docker_network, TEMPLATES),
            ForkObserver(self.docker_network, self.fork_observer_config),
            # Fluentd(self.docker_network, self.config_dir),
        ]
        if dns:
            services.append(DnsSeed(self.docker_network, TEMPLATES, self.config_dir))

        for service_obj in services:
            service_name = service_obj.__class__.__name__.lower()
            compose["services"][service_name] = service_obj.get_service()

        docker_compose_path = self.config_dir / "docker-compose.yml"
        try:
            with open(docker_compose_path, "w") as file:
                yaml.dump(compose, file)
            logger.info(f"Wrote file: {docker_compose_path}")
        except Exception as e:
            logger.error(
                f"An error occurred while writing to {docker_compose_path}: {e}"
            )

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

        prometheus_path = self.config_dir / "prometheus.yml"
        try:
            with open(prometheus_path, "w") as file:
                yaml.dump(config, file)
            logger.info(f"Wrote file: {prometheus_path}")
        except Exception as e:
            logger.error(f"An error occurred while writing to {prometheus_path}: {e}")


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

