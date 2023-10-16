"""
  Tanks are containerized bitcoind nodes
"""

import docker
import logging
import re
import shutil

from copy import deepcopy
from pathlib import Path
from docker.models.containers import Container

from templates import TEMPLATES
from warnet.utils import (
    exponential_backoff,
    generate_ipv4_addr,
    generate_as,
    sanitize_tc_netem_command,
    dump_bitcoin_conf,
    SUPPORTED_TAGS,
    get_architecture,
    set_execute_permission,
)


CONTAINER_PREFIX_BITCOIND = "tank"
CONTAINER_PREFIX_PROMETHEUS = "prometheus_exporter"
DOCKERFILE_NAME = "Dockerfile"
TORRC_NAME = "torrc"
WARNET_ENTRYPOINT_NAME = "warnet_entrypoint.sh"
DOCKER_ENTRYPOINT_NAME = "docker_entrypoint.sh"


logger = logging.getLogger("tank")


class Tank:
    DEFAULT_BUILD_ARGS = "--disable-tests --with-incompatible-bdb --without-gui --disable-bench --disable-fuzz-binary --enable-suppress-external-warnings --enable-debug "

    def __init__(self, index:int, config_dir: Path, warnet):
        self.index = index
        self.config_dir = config_dir
        self.warnet = warnet
        self.docker_network = warnet.docker_network
        self.bitcoin_network = warnet.bitcoin_network
        self.version = "25.0"
        self.conf = ""
        self.conf_file = None
        self.netem = None
        self.rpc_port = 18443
        self.rpc_user = "warnet_user"
        self.rpc_password = "2themoon"
        self.dockerfile_path = config_dir / DOCKERFILE_NAME
        self.torrc_path = config_dir / TORRC_NAME
        self.warnet_entrypoint = config_dir / WARNET_ENTRYPOINT_NAME
        self.docker_entrypoint = config_dir / DOCKER_ENTRYPOINT_NAME
        self._container = None
        self._suffix = None
        self._ipv4 = None
        self._a_system = None
        self._container_name = None
        self._exporter_name = None
        self.extra_build_args = ""

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
        index = int(index)
        config_dir = warnet.config_dir / str(f"{index:06}")
        config_dir.mkdir(parents=True, exist_ok=True)

        self = cls(index, config_dir, warnet)
        node = warnet.graph.nodes[index]
        version = node.get("version")
        if version:
            if not ("/" in version and "#" in version):
                if version not in SUPPORTED_TAGS:
                    raise Exception(
                        f"Unsupported version: can't be generated from Docker images: {version}"
                    )
            self.version = version
        self.conf = node.get("bitcoin_config")
        self.netem = node.get("tc_netem")
        self.extra_build_args = node.get("build_args", "")
        self.config_dir = self.warnet.config_dir / str(self.suffix)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        return self

    @classmethod
    def from_docker_compose_service(cls, service, network, config_dir, warnet):
        rex = fr"{network}_{CONTAINER_PREFIX_BITCOIND}_([0-9]{{6}})"
        match = re.match(rex, service["container_name"])
        if match is None:
            return None

        index = int(match.group(1))
        self = cls(index, config_dir, warnet)
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
    def autonomous_system(self):
        if self._a_system is None:
            self._a_system = generate_as(self.warnet)
        return self._a_system

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

    def copy_torrc(self):
        shutil.copyfile(Path(TEMPLATES) / TORRC_NAME, self.torrc_path)

    def copy_entrypoints(self):
        shutil.copyfile(Path(TEMPLATES) / WARNET_ENTRYPOINT_NAME, self.warnet_entrypoint)
        set_execute_permission(self.warnet_entrypoint)

        shutil.copyfile(Path(TEMPLATES) / DOCKER_ENTRYPOINT_NAME, self.docker_entrypoint)
        set_execute_permission(self.docker_entrypoint)

    def copy_dockerfile(self):
        assert self.dockerfile_path
        shutil.copyfile(Path(TEMPLATES) / DOCKERFILE_NAME, self.dockerfile_path)

    def copy_configs(self):
        self.copy_torrc()
        self.copy_entrypoints()
        self.copy_dockerfile()

    def add_services(self, services):
        assert self.index is not None
        assert self.conf_file is not None
        services[self.container_name] = {}

        self.copy_configs()

        # Setup bitcoind, either release binary or build from source
        if "/" and "#" in self.version:
            # it's a git branch, building step is necessary
            repo, branch = self.version.split("#")
            build = {
                "context": str(self.config_dir),
                "dockerfile": str(self.dockerfile_path),
                "args": {
                    "REPO": repo,
                    "BRANCH": branch,
                    "BUILD_ARGS": f"{self.DEFAULT_BUILD_ARGS + self.extra_build_args}",
                },
            }
        else:
            # assume it's a release version, get the binary
            build = {
                "context": str(self.config_dir),
                "dockerfile": str(self.dockerfile_path),
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
                "networks": {
                    self.docker_network: {
                        "ipv4_address": f"{self.ipv4}",
                    }
                },
                "labels": {"warnet": "tank"},
                "privileged": True,
                "cap_add": ["NET_ADMIN", "NET_RAW"],
                "depends_on": {
                    "fluentd": {
                        "condition": "service_healthy"
                    }
                },
                "healthcheck": {
                    "test": ["CMD", "pidof", "bitcoind"],
                    "interval": "5s",            # Check every 5 seconds
                    "timeout": "1s",             # Give the check 1 second to complete
                    "start_period": "5s",       # Start checking after 2 seconds
                    "retries": 3
                },
                "logging": {
                    "driver": "fluentd",
                    "options": {
                        "tag": "{{.Name}}"
                    }
                }
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
