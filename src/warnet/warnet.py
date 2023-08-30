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
from tempfile import mkdtemp
from templates import TEMPLATES
from typing import List
from warnet.tank import Tank
from warnet.utils import parse_bitcoin_conf

logger = logging.getLogger("Warnet")
TMPDIR_PREFIX = "warnet_tmp_"


class Warnet:
    def __init__(self):
        self.tmpdir: Path = Path(mkdtemp(prefix=TMPDIR_PREFIX))
        self.fork_observer_config = self.tmpdir / "fork_observer_config.toml"
        self.docker = docker.from_env()
        self.bitcoin_network:str = "regtest"
        self.docker_network:str = "warnet"
        self.subnet: str = "100.0.0.0/8"
        self.graph = None
        self.tanks: List[Tank] = []
        shutil.copy(TEMPLATES / "fork_observer_config.toml", self.fork_observer_config)
        logger.info(f"Created Warnet with temp directory {self.tmpdir}")

    def __str__(self) -> str:
        tanks_str = ',\n'.join([str(tank) for tank in self.tanks])
        return (f"Warnet(\n"
                f"\tTemp Directory: {self.tmpdir}\n"
                f"\tBitcoin Network: {self.bitcoin_network}\n"
                f"\tDocker Network: {self.docker_network}\n"
                f"\tSubnet: {self.subnet}\n"
                f"\tGraph: {self.graph}\n"
                f"\tTanks: [\n{tanks_str}\n"
                f"\t]\n"
                f")")

    @classmethod
    def from_graph_file(cls, graph_file: str, network: str = "warnet"):
        self = cls()
        self.docker_network = network
        self.graph = networkx.read_graphml(graph_file, node_type=int)
        self.tanks_from_graph()
        return self

    @classmethod
    def from_graph(cls, graph):
        self = cls()
        self.graph = graph
        self.tanks_from_graph()
        return self

    @classmethod
    def from_docker_env(cls, network_name):
        self = cls()
        self.docker_network = network_name
        index = 0
        while index <= 999999:
            try:
                self.tanks.append(Tank.from_docker_env(self.docker_network, index))
                index = index + 1
            except:
                assert index == len(self.tanks)
                break
        return self

    def tanks_from_graph(self):
        for node_id in self.graph.nodes():
            if int(node_id) != len(self.tanks):
                raise Exception(
                    f"Node ID in graph must be incrementing integers (got '{node_id}', expected '{len(self.tanks)}')"
                )
            self.tanks.append(Tank.from_graph_node(node_id, self))
        logger.info(f"Imported {len(self.tanks)} tanks from graph")

    def write_bitcoin_confs(self):
        with open(TEMPLATES / "bitcoin.conf", "r") as file:
            text = file.read()
        base_bitcoin_conf = parse_bitcoin_conf(text)
        for tank in self.tanks:
            tank.write_bitcoin_conf(base_bitcoin_conf)

    def apply_network_conditions(self):
        for tank in self.tanks:
            tank.apply_network_conditions()

    def connect_edges(self):
        for edge in self.graph.edges():
            (src, dst) = edge
            src_tank = self.tanks[int(src)]
            dst_ip = self.tanks[dst].ipv4
            logger.info(f"Using `addnode` to connect tanks {src} to {dst}")
            src_tank.exec(f"bitcoin-cli addpeeraddress {dst_ip} 18444")

    def docker_compose_up(self):
        command = ["docker-compose", "-p", "warnet", "up", "-d", "--build"]
        try:
            with subprocess.Popen(
                command,
                cwd=str(self.tmpdir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            ) as process:
                for line in process.stdout:
                    logger.info(line.decode().rstrip())
        except Exception as e:
            logger.error(
                f"An error occurred while executing `{' '.join(command)}` in {self.tmpdir}: {e}"
            )

    def write_docker_compose(self):
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

        # Add global services
        compose["services"]["prometheus"] = {
            "image": "prom/prometheus:latest",
            "container_name": "prometheus",
            "ports": ["9090:9090"],
            "volumes": [
                f"{self.tmpdir / 'prometheus.yml'}:/etc/prometheus/prometheus.yml"
            ],
            "command": ["--config.file=/etc/prometheus/prometheus.yml"],
            "networks": [self.docker_network],
        }
        compose["services"]["node-exporter"] = {
            "image": "prom/node-exporter:latest",
            "container_name": "node-exporter",
            "volumes": ["/proc:/host/proc:ro", "/sys:/host/sys:ro", "/:/rootfs:ro"],
            "command": ["--path.procfs=/host/proc", "--path.sysfs=/host/sys"],
            "networks": [self.docker_network],
        }
        compose["services"]["grafana"] = {
            "image": "grafana/grafana:latest",
            "container_name": "grafana",
            "ports": ["3000:3000"],
            "volumes": ["grafana-storage:/var/lib/grafana"],
            "networks": [self.docker_network],
        }
        compose["services"]["fork-observer"] = {
            "image": "will8clark/fork-observer:latest",
            "container_name": "fork-observer",
            "ports": ["12323:2323"],
            "volumes": [f"{self.fork_observer_config}:/fork-observer/config.toml"],
            "networks": [self.docker_network],
        }

        docker_compose_path = self.tmpdir / "docker-compose.yml"
        try:
            with open(docker_compose_path, "w") as file:
                yaml.dump(compose, file)
            logger.info(f"Wrote file: {docker_compose_path}")
        except Exception as e:
            logger.error(
                f"An error occurred while writing to {docker_compose_path}: {e}"
            )

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

        for tank in self.tanks:
            tank.add_scrapers(config["scrape_configs"])

        prometheus_path = self.tmpdir / "prometheus.yml"
        try:
            with open(prometheus_path, "w") as file:
                yaml.dump(config, file)
            logger.info(f"Wrote file: {prometheus_path}")
        except Exception as e:
            logger.error(f"An error occurred while writing to {prometheus_path}: {e}")
