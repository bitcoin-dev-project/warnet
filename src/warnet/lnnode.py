from abc import ABC, abstractmethod

from warnet.backend.kubernetes_backend import KubernetesBackend
from warnet.services import ServiceType
from warnet.utils import exponential_backoff, handle_json

from .status import RunningStatus


class LNNode(ABC):
    @abstractmethod
    def __init__(self, warnet, tank, backend: KubernetesBackend, options):
        pass

    @property
    def status(self) -> RunningStatus:
        return self.warnet.container_interface.get_status(self.tank.index, ServiceType.LIGHTNING)

    @property
    def cb_status(self) -> RunningStatus:
        if not self.cb:
            return None
        return self.warnet.container_interface.get_status(
            self.tank.index, ServiceType.CIRCUITBREAKER
        )

    @abstractmethod
    def get_conf(self, ln_container_name, tank_container_name) -> str:
        pass

    @exponential_backoff(max_retries=20, max_delay=300)
    @handle_json
    @abstractmethod
    def lncli(self, cmd) -> dict:
        pass

    @abstractmethod
    def getnewaddress(self):
        pass

    @abstractmethod
    def get_pub_key(self):
        pass

    @abstractmethod
    def getURI(self):
        pass

    @abstractmethod
    def get_wallet_balance(self) -> int:
        pass

    @abstractmethod
    def open_channel_to_tank(self, index: int, channel_open_data: str) -> str:
        """Return the channel point in the form txid:output_index"""
        pass

    @abstractmethod
    def update_channel_policy(self, chan_point: str, policy: str) -> str:
        pass

    @abstractmethod
    def get_graph_nodes(self) -> list[str]:
        pass

    @abstractmethod
    def get_graph_channels(self) -> list[dict]:
        pass

    @abstractmethod
    def get_peers(self) -> list[str]:
        pass

    def connect_to_tank(self, index):
        tank = self.warnet.tanks[index]
        uri = tank.lnnode.getURI()
        res = self.lncli(f"connect {uri}")
        return res

    @abstractmethod
    def generate_cli_command(self, command: list[str]):
        pass

    @abstractmethod
    def export(self, config: object, tar_file):
        pass


def lnd_to_cl_scid(id) -> str:
    s = int(id, 10)
    block = s >> 40
    tx = s >> 16 & 0xFFFFFF
    output = s & 0xFFFF
    return f"{block}x{tx}x{output}"


def cl_to_lnd_scid(s) -> int:
    s = [int(i) for i in s.split("x")]
    return (s[0] << 40) | (s[1] << 16) | s[2]
