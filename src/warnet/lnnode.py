
import docker
from docker.models.containers import Container
from warnet.utils import (
    generate_ipv4_addr
)

CONTAINER_PREFIX_LN = "ln"

class LNNode:
    def __init__(self, warnet, tank, impl):
        self.warnet = warnet
        self.tank = tank
        assert impl == "lnd"
        self.impl = impl
        self._container = None
        self.container_name = f"{self.tank.docker_network}_{CONTAINER_PREFIX_LN}_{self.tank.suffix}"
        self.ipv4 = generate_ipv4_addr(self.warnet.subnet)

    @property
    def container(self) -> Container:
        if self._container is None:
            try:
                self._container = docker.from_env().containers.get(self.container_name)
            except:
                pass
        return self._container

    def add_services(self, services):
        # These args are appended to the Dockerfile `ENTRYPOINT ["lnd"]`
        args = [
            "--noseedbackup",
            "--norest",
            "--debuglevel=debug",
            "--accept-keysend",
            "--bitcoin.active",
            "--bitcoin.regtest",
            "--bitcoin.node=bitcoind",
            f"--bitcoind.rpcuser={self.tank.rpc_user}",
            f"--bitcoind.rpcpass={self.tank.rpc_password}",
            f"--bitcoind.rpchost={self.tank.ipv4}:{self.tank.rpc_port}",
            f"--bitcoind.zmqpubrawblock=tcp://{self.tank.ipv4}:28332",
            f"--bitcoind.zmqpubrawtx=tcp://{self.tank.ipv4}:28333",
            f"--externalip={self.ipv4}"
        ]
        services[self.container_name] = {
            "container_name": self.container_name,
            "image": "lightninglabs/lnd:v0.17.0-beta",
            "command": " ".join(args),
            "networks": {
                self.tank.docker_network: {
                    "ipv4_address": f"{self.ipv4}",
                }
            },
            "tank": {
                "index": self.tank.index,
                "container_name": self.tank.container_name,
                "ipv4_address": self.tank.ipv4
            }
        }
