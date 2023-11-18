
import docker
import json
import os
from docker.models.containers import Container
from warnet.utils import (
    exponential_backoff,
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
        self.container_name = f"{self.tank.network_name}_{CONTAINER_PREFIX_LN}_{self.tank.suffix}"
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
            f"--externalip={self.ipv4}",
            f"--rpclisten=0.0.0.0:10009",
            f"--alias={self.container_name}"
        ]
        services[self.container_name] = {
            "container_name": self.container_name,
            "image": "lightninglabs/lnd:v0.17.0-beta",
            "command": " ".join(args),
            "networks": {
                self.tank.network_name: {
                    "ipv4_address": f"{self.ipv4}",
                }
            },
            "labels": {
                "tank_index": self.tank.index,
                "tank_container_name": self.tank.container_name,
                "tank_ipv4_address": self.tank.ipv4
            }
        }

    @exponential_backoff(max_retries=20, max_delay=300)
    def lncli(self, cmd):
        cmd = f"lncli --network=regtest {cmd}"
        result = self.container.exec_run(cmd=cmd)
        if result.exit_code != 0:
            raise Exception(
                f"Command failed with exit code {result.exit_code}: {result.output.decode('utf-8')}"
            )
        return result.output.decode("utf-8")

    def getnewaddress(self):
        res = json.loads(self.lncli("newaddress p2wkh"))
        return res["address"]

    def getURI(self):
        res = json.loads(self.lncli("getinfo"))
        return res["uris"][0]

    def open_channel_to_tank(self, index, amt):
        tank = self.warnet.tanks[index]
        [pubkey, host] = tank.lnnode.getURI().split('@')
        res = json.loads(self.lncli(f"openchannel --node_key={pubkey} --connect={host} --local_amt={amt}"))
        return res

    def connect_to_tank(self, index):
        tank = self.warnet.tanks[index]
        uri = tank.lnnode.getURI()
        res = self.lncli(f"connect {uri}")
        return res

    def export(self, config, subdir):
        macaroon_filename = f"{self.container_name}_admin.macaroon"
        cert_filename = f"{self.container_name}_tls.cert"
        macaroon_path = os.path.join(subdir, macaroon_filename)
        cert_path = os.path.join(subdir, cert_filename)
        macaroon = self.warnet.container_interface.get_file_from_container(self.container, "/root/.lnd/data/chain/bitcoin/regtest/admin.macaroon")
        cert = self.warnet.container_interface.get_file_from_container(self.container, "/root/.lnd/tls.cert")

        with open(macaroon_path, "wb") as f:
            f.write(macaroon)

        with open(cert_path, "wb") as f:
            f.write(cert)

        config["nodes"].append({
            "id": self.container_name,
            "address": f"https://{self.ipv4}:10009",
            "macaroon": macaroon_path,
            "cert": cert_path
        })

