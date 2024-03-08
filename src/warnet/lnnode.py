import os

from backends import BackendInterface, ServiceType
from warnet.utils import exponential_backoff, handle_json

from .status import RunningStatus


class LNNode:
    def __init__(self, warnet, tank, impl, image, backend: BackendInterface, cb=None):
        self.warnet = warnet
        self.tank = tank
        assert impl == "lnd"
        self.impl = impl
        self.image = "lightninglabs/lnd:v0.17.0-beta"
        if image:
            self.image = image
        self.backend_interface = backend
        self.rpc_port = 10009
        self.cb = cb
        self.hostname = self.backend_interface.get_container_name(
            self.tank.index, ServiceType.LIGHTNING
        )
        self._pubkey: str | None = None

    def __str__(self):
        return f"LNNode: index={self.tank.index}, rpc_port={self.rpc_port}"

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

    @exponential_backoff(max_retries=20, max_delay=300)
    @handle_json
    def lncli(self, cmd) -> dict:
        cmd = f"lncli --network=regtest {cmd}"
        return self.backend_interface.exec_run(self.tank.index, ServiceType.LIGHTNING, cmd)

    def getnewaddress(self):
        res = self.lncli("newaddress p2wkh")
        return res["address"]

    @property
    def pubkey(self):
        if not self._pubkey:
            self._pubkey = self.lncli("getinfo")["identity_pubkey"]
        return self._pubkey

    def get_wallet_balance(self):
        res = self.lncli("walletbalance")
        return res

    def open_channel_to_tank(self, index, amt):
        tank = self.warnet.tanks[index]
        pubkey = tank.lnnode.pubkey
        host = tank.lnnode.hostname
        res = self.lncli(f"openchannel --node_key={pubkey} --connect={host} --local_amt={amt}")
        return res

    def connect_to_tank(self, index):
        tank = self.warnet.tanks[index]
        pubkey = tank.lnnode.pubkey
        host = tank.lnnode.hostname
        res = self.lncli(f"connect {pubkey}@{host}")
        return res

    def generate_cli_command(self, command: list[str]):
        network = f"--network={self.tank.warnet.bitcoin_network}"
        cmd = f"{network} {' '.join(command)}"
        match self.impl:
            case "lnd":
                cmd = f"lncli {cmd}"
            case "cln":
                cmd = f"lightning-cli {cmd}"
            case _:
                raise Exception(f"Unsupported LN implementation: {self.impl}")
        return cmd

    def export(self, config, subdir):
        macaroon_filename = f"{self.hostname}_admin.macaroon"
        cert_filename = f"{self.hostname}_tls.cert"
        macaroon_path = os.path.join(subdir, macaroon_filename)
        cert_path = os.path.join(subdir, cert_filename)
        macaroon = self.backend_interface.get_file(
            self.tank.index,
            ServiceType.LIGHTNING,
            "/root/.lnd/data/chain/bitcoin/regtest/admin.macaroon",
        )
        cert = self.backend_interface.get_file(
            self.tank.index, ServiceType.LIGHTNING, "/root/.lnd/tls.cert"
        )

        with open(macaroon_path, "wb") as f:
            f.write(macaroon)

        with open(cert_path, "wb") as f:
            f.write(cert)

        config["nodes"].append(
            {
                "id": self.hostname,
                # TODO: What does this break?
                # "address": f"https://{self.ipv4}:{self.rpc_port}",
                "macaroon": macaroon_path,
                "cert": cert_path,
            }
        )
