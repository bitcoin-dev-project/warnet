"""
Tanks are containerized bitcoind nodes
"""

import logging

from pathlib import Path
from warnet.lnnode import LNNode
from warnet.utils import (
    exponential_backoff,
    generate_as,
    generate_ipv4_addr,
    sanitize_tc_netem_command,
    SUPPORTED_TAGS,
)
from backends import ServiceType
from .status import RunningStatus


CONTAINER_PREFIX_PROMETHEUS = "prometheus_exporter"


logger = logging.getLogger("tank")


class Tank:
    DEFAULT_BUILD_ARGS = "--disable-tests --with-incompatible-bdb --without-gui --disable-bench --disable-fuzz-binary --enable-suppress-external-warnings --enable-debug "

    def __init__(self, index: int, config_dir: Path, warnet):
        self.index = index
        self.config_dir = config_dir
        self.warnet = warnet
        self.network_name = warnet.network_name
        self.bitcoin_network = warnet.bitcoin_network
        self.version = "25.1"
        self.conf = ""
        self.conf_file = None
        self.netem = None
        self.exporter = False
        self.rpc_port = 18443
        self.rpc_user = "warnet_user"
        self.rpc_password = "2themoon"
        self._suffix = None
        self._ipv4 = None
        self._a_system = None
        self._exporter_name = None
        self.extra_build_args = ""
        self.lnnode = None
        self.zmqblockport = 28332
        self.zmqtxport = 28333

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
    def from_graph_node(cls, index, warnet, tank=None):
        assert index is not None
        index = int(index)
        config_dir = warnet.config_dir / str(f"{index:06}")
        config_dir.mkdir(parents=True, exist_ok=True)

        self = tank
        if self is None:
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
        self.conf = node.get("bitcoin_config", self.conf)
        self.netem = node.get("tc_netem", self.netem)
        self.exporter = node.get("exporter", self.exporter)
        self.extra_build_args = node.get("build_args", self.extra_build_args)

        if "ln" in node:
            self.lnnode = LNNode(self.warnet, self, node["ln"], self.warnet.container_interface)

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
    def exporter_name(self):
        if self._exporter_name is None:
            self._exporter_name = f"{self.network_name}-{CONTAINER_PREFIX_PROMETHEUS}-{self.suffix}"
        return self._exporter_name

    @property
    def status(self) -> RunningStatus:
        return self.warnet.container_interface.get_status(self.index, ServiceType.BITCOIN)

    @property
    def autonomous_system(self) -> int:
        if self._a_system is None:
            self._a_system = generate_as()
        return self._a_system

    @exponential_backoff()
    def exec(self, cmd: str, user: str = "root"):
        return self.warnet.container_interface.exec_run(
            self.index, ServiceType.BITCOIN, cmd=cmd, user=user
        )

    def apply_network_conditions(self):
        if self.netem is None:
            return

        if not sanitize_tc_netem_command(self.netem):
            logger.warning(
                f"Not applying unsafe tc-netem conditions to tank {self.index}: `{self.netem}`"
            )
            return

        # Apply the network condition to the container
        try:
            self.exec(self.netem)
            logger.info(
                f"Successfully applied network conditions to tank {self.index}: `{self.netem}`"
            )
        except Exception as e:
            logger.error(
                f"Error applying network conditions to tank {self.index}: `{self.netem}` ({e})"
            )

    def export(self, config, subdir):
        if self.lnnode is not None:
            self.lnnode.export(config, subdir)
