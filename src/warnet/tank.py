"""
Tanks are containerized bitcoind nodes
"""

import logging

from .services import ServiceType
from .status import RunningStatus
from .utils import (
    SUPPORTED_TAGS,
    exponential_backoff,
    generate_ipv4_addr,
    sanitize_tc_netem_command,
)

CONTAINER_PREFIX_PROMETHEUS = "prometheus_exporter"

logger = logging.getLogger("tank")

CONFIG_BASE = " ".join(
    [
        "-regtest=1",
        "-checkmempool=0",
        "-acceptnonstdtxn=1",
        "-debuglogfile=0",
        "-logips=1",
        "-logtimemicros=1",
        "-capturemessages=1",
        "-rpcallowip=0.0.0.0/0",
        "-rpcbind=0.0.0.0",
        "-fallbackfee=0.00001000",
        "-listen=1",
    ]
)


class Tank:
    DEFAULT_BUILD_ARGS = "--disable-tests --with-incompatible-bdb --without-gui --disable-bench --disable-fuzz-binary --enable-suppress-external-warnings --enable-debug "

    def __init__(self, index: int, warnet):
        from warnet.lnnode import LNNode

        self.index = index
        self.warnet = warnet
        self.network_name = warnet.network_name
        self.bitcoin_network = warnet.bitcoin_network
        self.version: str = ""
        self.image: str = ""
        self.bitcoin_config = ""
        self.netem = None
        self.exporter = False
        self.collect_logs = False
        self.build_args = ""
        self.lnnode: LNNode | None = None
        self.rpc_port = 18443
        self.rpc_user = "warnet_user"
        self.rpc_password = "2themoon"
        self.zmqblockport = 28332
        self.zmqtxport = 28333
        self._suffix = None
        self._ipv4 = None
        self._exporter_name = None
        # index of integers imported from graph file
        # indicating which tanks to initially connect to
        self.init_peers = []

    def _parse_version(self, version):
        if not version:
            return
        if version not in SUPPORTED_TAGS and not ("/" in version and "#" in version):
            raise Exception(
                f"Unsupported version: can't be generated from Docker images: {self.version}"
            )
        self.version = version

    def parse_graph_node(self, node):
        # Dynamically parse properties based on the schema
        graph_properties = {}
        for property, specs in self.warnet.graph_schema["node"]["properties"].items():
            value = node.get(property, specs.get("default"))
            if property == "version":
                self._parse_version(value)
            setattr(self, property, value)
            graph_properties[property] = value

        if self.version and self.image:
            raise Exception(
                f"Tank has {self.version=:} and {self.image=:} supplied and can't be built. Provide one or the other."
            )

        # Special handling for complex properties
        if "ln" in node:
            options = {
                "impl": node["ln"],
                "cb_image": node.get("ln_cb_image", None),
                "ln_config": node.get("ln_config", ""),
            }
            from warnet.cln import CLNNode
            from warnet.lnd import LNDNode

            if options["impl"] == "lnd":
                options["ln_image"] = node.get("ln_image", "lightninglabs/lnd:v0.18.0-beta")
                self.lnnode = LNDNode(self.warnet, self, self.warnet.container_interface, options)
            elif options["impl"] == "cln":
                options["ln_image"] = node.get("ln_image", "elementsproject/lightningd:v23.11")
                self.lnnode = CLNNode(self.warnet, self, self.warnet.container_interface, options)
            else:
                raise Exception(f"Unsupported Lightning Network implementation: {options['impl']}")

        logger.debug(
            f"Parsed graph node: {self.index} with attributes: {[f'{key}={value}' for key, value in graph_properties.items()]}"
        )

    @classmethod
    def from_graph_node(cls, index, warnet, tank=None):
        assert index is not None
        index = int(index)
        self = tank
        if self is None:
            self = cls(index, warnet)
        node = warnet.graph.nodes[index]
        self.parse_graph_node(node)
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

    @exponential_backoff()
    def exec(self, cmd: str):
        return self.warnet.container_interface.exec_run(self.index, ServiceType.BITCOIN, cmd=cmd)

    def get_dns_addr(self) -> str:
        dns_addr = self.warnet.container_interface.get_tank_dns_addr(self.index)
        return dns_addr

    def get_ip_addr(self) -> str:
        ip_addr = self.warnet.container_interface.get_tank_ip_addr(self.index)
        return ip_addr

    def get_bitcoin_conf(self, nodes: list[str]) -> str:
        conf = CONFIG_BASE
        conf += f" -rpcuser={self.rpc_user}"
        conf += f" -rpcpassword={self.rpc_password}"
        conf += f" -rpcport={self.rpc_port}"
        conf += f" -zmqpubrawblock=tcp://0.0.0.0:{self.zmqblockport}"
        conf += f" -zmqpubrawtx=tcp://0.0.0.0:{self.zmqtxport}"
        conf += " " + self.bitcoin_config
        for node in nodes:
            conf += f" -addnode={node}"
        return conf

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

    def export(self, config: object, tar_file):
        if self.lnnode is not None:
            self.lnnode.export(config, tar_file)
