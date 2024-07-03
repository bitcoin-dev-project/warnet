from backend.kubernetes_backend import KubernetesBackend
from warnet.services import ServiceType
from warnet.utils import exponential_backoff, handle_json

from .status import RunningStatus


class LNNode:
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

    def get_conf(self, ln_container_name, tank_container_name) -> str:
        pass

    @exponential_backoff(max_retries=20, max_delay=300)
    @handle_json
    def lncli(self, cmd) -> dict:
        pass

    def getnewaddress(self):
        pass

    def get_pub_key(self):
        pass

    def getURI(self):
        pass

    def get_wallet_balance(self) -> int:
        pass

    # returns the channel point in the form txid:output_index
    def open_channel_to_tank(self, index: int, channel_open_data: str) -> str:
        pass

    def update_channel_policy(self, chan_point: str, policy: str) -> str:
        pass

    def get_graph_nodes(self) -> list[str]:
        pass

    def get_graph_channels(self) -> list[dict]:
        pass

    def get_peers(self) -> list[str]:
        pass

    def connect_to_tank(self, index):
        tank = self.warnet.tanks[index]
        uri = tank.lnnode.getURI()
        res = self.lncli(f"connect {uri}")
        return res

    def generate_cli_command(self, command: list[str]):
        pass

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
