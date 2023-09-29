"""
  Tanks are containerized bitcoind nodes
"""

import docker
import logging
import shutil
from copy import deepcopy
from pathlib import Path
import re
from docker.models.containers import Container
from templates import TEMPLATES
from services.dns_seed import IP_ADDR as DNS_IP_ADDR
from warnet.utils import (
    exponential_backoff,
    generate_ipv4_addr,
    sanitize_tc_netem_command,
    dump_bitcoin_conf,
    SUPPORTED_TAGS,
    get_architecture,
)

CONTAINER_PREFIX_BITCOIND = "tank"
CONTAINER_PREFIX_PROMETHEUS = "prometheus_exporter"
logger = logging.getLogger("tank")


class Tank:
    def __init__(self):
        self.warnet = None
        self.docker_network = "warnet"
        self.bitcoin_network = "regtest"
        self.index = None
        self.version = "25.0"
        self.conf = ""
        self.conf_file = None
        self.torrc_file = None
        self.netem = None
        self.rpc_port = 18443
        self.rpc_user = "warnet_user"
        self.rpc_password = "2themoon"
        self._container = None
        self._suffix = None
        self._ipv4 = None
        self._container_name = None
        self._exporter_name = None
        self.config_dir = Path()

    def __str__(self) -> str:
        return (
            f"Tank(\n"
            f"\tIndex: {self.index}\n"
            f"\tVersion: {self.version}\n"
            f"\tConf: {self.conf}\n"
            f"\tConf File: {self.conf_file}\n"
            f"\tNetem: {self.netem}\n"
            f"\tIPv4: {self._ipv4}\n"
            f"\t)"
        )

    @classmethod
    def from_graph_node(cls, index, warnet):
        assert index is not None

        self = cls()
        self.warnet = warnet
        self.docker_network = warnet.docker_network
        self.bitcoin_network = warnet.bitcoin_network
        self.index = int(index)
        node = warnet.graph.nodes[index]
        if "version" in node:
            if not "/" and "#" in self.version:
                if node["version"] not in SUPPORTED_TAGS:
                    raise Exception(
                        f"Unsupported version: can't be generated from Docker images: {node['version']}"
                    )
            self.version = node["version"]
        if "bitcoin_config" in node:
            self.conf = node["bitcoin_config"]
        if "tc_netem" in node:
            self.netem = node["tc_netem"]
        self.config_dir = self.warnet.config_dir / str(self.suffix)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.write_torrc()
        return self

    @classmethod
    def from_docker_compose_service(cls, service, network):
        rex = fr"{network}_{CONTAINER_PREFIX_BITCOIND}_([0-9]{{6}})"
        match = re.match(rex, service["container_name"])
        if match is None:
            return None

        self = cls()
        self.index = int(match.group(1))
        self.docker_network = network
        self._ipv4 = service["networks"][self.docker_network]["ipv4_address"]
        if "BITCOIN_VERSION" in service["build"]["args"]:
            self.version = service["build"]["args"]["BITCOIN_VERSION"]
        else:
            self.version = f"{service['build']['args']['REPO']}#{service['build']['args']['BRANCH']}"
        return self

    @property
    def suffix(self):
        if self._suffix is None:
            self._suffix = f"{self.index:06}"
        return self._suffix

    @property
    def ipv4(self):
        if self._ipv4 is None:
            self._ipv4 = generate_ipv4_addr(self.warnet.subnet)
        return self._ipv4

    @property
    def container_name(self):
        if self._container_name is None:
            self._container_name = (
                f"{self.docker_network}_{CONTAINER_PREFIX_BITCOIND}_{self.suffix}"
            )
        return self._container_name

    @property
    def exporter_name(self):
        if self._exporter_name is None:
            self._exporter_name = (
                f"{self.docker_network}_{CONTAINER_PREFIX_PROMETHEUS}_{self.suffix}"
            )
        return self._exporter_name

    @property
    def container(self) -> Container:
        if self._container is None:
            try:
                self._container = docker.from_env().containers.get(self.container_name)
            except:
                pass
        return self._container

    @exponential_backoff()
    def exec(self, cmd: str, user: str = "root"):
        result = self.container.exec_run(cmd=cmd, user=user)
        if result.exit_code != 0:
            raise Exception(
                f"Command failed with exit code {result.exit_code}: {result.output.decode('utf-8')}"
            )
        return result.output.decode("utf-8")

    def apply_network_conditions(self):
        if self.netem is None:
            return

        if not sanitize_tc_netem_command(self.netem):
            logger.warning(
                f"Not applying unsafe tc-netem conditions to container {self.container_name}: `{self.netem}`"
            )
            return

        # Apply the network condition to the container
        try:
            self.exec(self.netem)
            logger.info(
                f"Successfully applied network conditions to {self.container_name}: `{self.netem}`"
            )
        except Exception as e:
            logger.error(
                f"Error applying network conditions to {self.container_name}: `{self.netem}` ({e})"
            )

    def write_bitcoin_conf(self, base_bitcoin_conf):
        conf = deepcopy(base_bitcoin_conf)
        options = self.conf.split(",")
        for option in options:
            option = option.strip()
            if option:
                if "=" in option:
                    key, value = option.split("=")
                else:
                    key, value = option, "1"
                conf[self.bitcoin_network].append((key, value))

        conf[self.bitcoin_network].append(("rpcuser", self.rpc_user))
        conf[self.bitcoin_network].append(("rpcpassword", self.rpc_password))
        conf[self.bitcoin_network].append(("rpcport", self.rpc_port))

        conf_file = dump_bitcoin_conf(conf)
        path = self.config_dir / f"bitcoin.conf"
        logger.info(f"Wrote file {path}")
        with open(path, "w") as file:
            file.write(conf_file)
        self.conf_file = path

    def write_torrc(self):
        src_tor_conf_file = TEMPLATES / "torrc"

        dest_path = self.config_dir / "torrc"
        shutil.copyfile(src_tor_conf_file, dest_path)
        self.torrc_file = dest_path

    def add_services(self, services):
        assert self.index is not None
        assert self.conf_file is not None
        services[self.container_name] = {}

        # Setup bitcoind, either release binary or build from source
        if "/" and "#" in self.version:
            # it's a git branch, building step is necessary
            repo, branch = self.version.split("#")
            build = {
                "context": str(TEMPLATES),
                "dockerfile": str(TEMPLATES / "Dockerfile"),
                "args": {
                    "REPO": repo,
                    "BRANCH": branch,
                },
            }
        else:
            # assume it's a release version, get the binary
            build = {
                "context": str(TEMPLATES),
                "dockerfile": str(TEMPLATES / f"Dockerfile"),
                "args": {
                    "ARCH": get_architecture(),
                    "BITCOIN_URL": "https://bitcoincore.org/bin",
                    "BITCOIN_VERSION": f"{self.version}",
                },
            }
        # Add the bitcoind service
        services[self.container_name].update(
            {
                "container_name": self.container_name,
                "build": build,
                "volumes": [
                    f"{self.conf_file}:/home/bitcoin/.bitcoin/bitcoin.conf",
                    f"{self.torrc_file}:/etc/tor/torrc_original",
                ],
                "networks": {
                    self.docker_network: {
                        "ipv4_address": f"{self.ipv4}",
                    }
                },
                "extra_hosts": [f"dummySeed.invalid:{DNS_IP_ADDR}"], # hack to trick regtest into doing dns lookups
                "labels": {"warnet": "tank"},
                "privileged": True,
                "cap_add": ["NET_ADMIN", "NET_RAW"],
                "dns": [DNS_IP_ADDR],
                # "depends_on": ["fluentd"],
                # "logging": {
                #     "driver": "fluentd",
                #     "options": {
                #         "fluentd-address": f"{FLUENT_IP}:24224",
                #         "tag": "{{.Name}}"
                #     }
                # }
            }
        )

        # grep: disable-exporters
        # Add the prometheus data exporter in a neighboring container
        # services[self.exporter_name] = {
        #     "image": "jvstein/bitcoin-prometheus-exporter",
        #     "container_name": self.exporter_name,
        #     "environment": {
        #         "BITCOIN_RPC_HOST": self.container_name,
        #         "BITCOIN_RPC_PORT": self.rpc_port,
        #         "BITCOIN_RPC_USER": self.rpc_user,
        #         "BITCOIN_RPC_PASSWORD": self.rpc_password,
        #     },
        #     "ports": [f"{8335 + self.index}:9332"],
        #     "networks": [self.docker_network],
        # }

    def add_scrapers(self, scrapers):
        scrapers.append(
            {
                "job_name": self.container_name,
                "scrape_interval": "5s",
                "static_configs": [{"targets": [f"{self.exporter_name}:9332"]}],
            }
        )
