"""
  Tanks are containerized bitcoind nodes
"""

import docker
import logging
from copy import deepcopy
from templates import TEMPLATES
from warnet.utils import (
    get_architecture,
    generate_ipv4_addr,
    sanitize_tc_netem_command,
    dump_bitcoin_conf
)

CONTAINER_PREFIX_BITCOIND = "tank"
CONTAINER_PREFIX_PROMETHEUS = "prometheus_exporter"

class Tank:
    def __init__(self):
        self.warnet = None
        self.docker_network = "warnet"
        self.bitcoin_network = "regtest"
        self.index = None
        self.version = "25.0"
        self.conf = ""
        self.conf_file = None
        self.netem = None
        self.rpc_port = 18443
        self.rpc_user = "warnet_user"
        self.rpc_password = "2themoon"
        self._container = None
        self._suffix = None
        self._ipv4 = None
        self._bitcoind_name = None
        self._exporter_name = None

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
            self.version = node["version"]
        if "bitcoin_config" in node:
            self.conf = node["bitcoin_config"]
        if "tc_netem" in node:
            self.netem = node["tc_netem"]
        return self

    @classmethod
    def from_docker_env(cls, network, index):
        self = cls()
        self.index = int(index)
        self.docker_network = network
        self._ipv4 = self.container.attrs["NetworkSettings"]["Networks"][self.docker_network]["IPAddress"]
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
    def bitcoind_name(self):
        if self._bitcoind_name is None:
            self._bitcoind_name = f"{CONTAINER_PREFIX_BITCOIND}_{self.suffix}"
        return self._bitcoind_name

    @property
    def exporter_name(self):
        if self._exporter_name is None:
            self._exporter_name = f"{CONTAINER_PREFIX_PROMETHEUS}_{self.suffix}"
        return self._exporter_name

    @property
    def container(self):
        if self._container is None:
            self._container = docker.from_env().containers.get(self.bitcoind_name)
        return self._container

    def exec(self, cmd):
        return self.container.exec_run(cmd)

    def apply_network_conditions(self):
        if self.netem is None:
            return

        if not sanitize_tc_netem_command(self.netem):
            logging.warning(f"Not applying unsafe tc-netem conditions to container {self.bitcoind_name}: `{self.netem}`")
            return

        # Apply the network condition to the container
        rcode, result = self.exec(self.netem)
        if rcode == 0:
            logging.info(f"Successfully applied network conditions to {self.bitcoind_name}: `{self.netem}`")
        else:
            logging.error(f"Error applying network conditions to {self.bitcoind_name}: `{self.netem}` ({result})")

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
        path = self.warnet.tmpdir / f"bitcoin.conf.{self.suffix}"
        logging.info(f"Wrote file {path}")
        with open(path, 'w') as file:
            file.write(conf_file)
        self.conf_file = path

    def add_services(self, services):
        assert self.index is not None
        assert self.conf_file is not None

        # Setup bitcoind, either release binary or build from source
        if "/" and "#" in self.version:
            # it's a git branch, building step is necessary
            repo, branch = self.version.split("#")
            build = {
                "context": ".",
                "dockerfile": str(TEMPLATES / "Dockerfile"),
                "args": {
                    "REPO": repo,
                    "BRANCH": branch,
                }
            }
        else:
            # assume it's a release version, get the binary
            arch = get_architecture()
            build = {
                "context": ".",
                "dockerfile": str(TEMPLATES / "Dockerfile"),
                "args": {
                    "ARCH": arch,
                    "BITCOIN_VERSION": self.version,
                    "BITCOIN_URL": f"https://bitcoincore.org/bin/bitcoin-core-{self.version}/bitcoin-{self.version}-{arch}-linux-gnu.tar.gz"
                }
            }

        # Add the bitcoind service
        services[self.bitcoind_name] = {
            "container_name": self.bitcoind_name,

            "build": build,
            "volumes": [
                f"{self.conf_file}:/root/.bitcoin/bitcoin.conf"
            ],
            "networks": {
                self.docker_network: {
                    "ipv4_address": f"{self.ipv4}",
                }
            },
            "privileged": True,
        }

        # Add the prometheus data exporter in a neighboring container
        services[self.exporter_name] = {
            "image": "jvstein/bitcoin-prometheus-exporter",
            "container_name": self.exporter_name,
            "environment": {
                "BITCOIN_RPC_HOST": self.bitcoind_name,
                "BITCOIN_RPC_PORT": self.rpc_port,
                "BITCOIN_RPC_USER": self.rpc_user,
                "BITCOIN_RPC_PASSWORD": self.rpc_password,
            },
            "ports": [f"{8335 + self.index}:9332"],
            "networks": [
                self.docker_network
            ]
        }

    def add_scrapers(self, scrapers):
        scrapers.append({
            "job_name": self.bitcoind_name,
            "scrape_interval": "5s",
            "static_configs": [
                {"targets": [f"{self.exporter_name}:9332"]}
            ]
        })

