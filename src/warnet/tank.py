"""
Tanks are containerized bitcoind nodes
"""

import logging

from pathlib import Path

from warnet.utils import (
    exponential_backoff,
    generate_ipv4_addr,
    sanitize_tc_netem_command,
    SUPPORTED_TAGS,
)


CONTAINER_PREFIX_BITCOIND = "tank"
CONTAINER_PREFIX_PROMETHEUS = "prometheus_exporter"


logger = logging.getLogger("tank")


class Tank:
    DEFAULT_BUILD_ARGS = "--disable-tests --with-incompatible-bdb --without-gui --disable-bench --disable-fuzz-binary --enable-suppress-external-warnings --enable-debug "

    def __init__(self, index:int, config_dir: Path, warnet):
        self.index = index
        self.config_dir = config_dir
        self.warnet = warnet
        self.network_name = warnet.network_name
        self.bitcoin_network = warnet.bitcoin_network
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
        if node.get("bitcoin_config"):
            self.conf = node.get("bitcoin_config")
        if node.get("tc_netem"):
            self.netem = node.get("tc_netem")
        if node.get("build_args"):
            self.extra_build_args = node.get("build_args")
        self.config_dir = self.warnet.config_dir / str(self.suffix)
        self.config_dir.mkdir(parents=True, exist_ok=True)
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
                f"{self.network_name}_{CONTAINER_PREFIX_BITCOIND}_{self.suffix}"
            )
        return self._container_name

    @property
    def exporter_name(self):
        if self._exporter_name is None:
            self._exporter_name = (
                f"{self.network_name}_{CONTAINER_PREFIX_PROMETHEUS}_{self.suffix}"
            )
        return self._exporter_name

    @property
    def container(self):
        if self._container is None:
            try:
                self._container = self.warnet.container_interface.get_container(self.container_name)
            except:
                pass
        return self._container

    @exponential_backoff()
    def exec(self, cmd: str, user: str = "root"):
        return self.warnet.container_interface.exec_run(self.container_name, cmd=cmd, user=user)

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

