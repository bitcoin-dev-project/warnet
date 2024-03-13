import os

from backends import BackendInterface, ServiceType
from warnet.utils import exponential_backoff, generate_ipv4_addr, handle_json

from .status import RunningStatus

LND_CONFIG_BASE = " ".join([
    "--noseedbackup",
    "--norest",
    "--debuglevel=debug",
    "--accept-keysend",
    "--bitcoin.active",
    "--bitcoin.regtest",
    "--bitcoin.node=bitcoind",
    "--maxpendingchannels=64"
])

class LNNode:
    def __init__(self, warnet, tank, backend: BackendInterface, options):
        self.warnet = warnet
        self.tank = tank
        self.backend = backend
        self.impl = options["impl"]
        self.image = options["ln_image"]
        self.cb = options["cb_image"]
        self.ln_config = options["ln_config"]
        self.ipv4 = generate_ipv4_addr(self.warnet.subnet)
        self.rpc_port = 10009

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
        if self.impl == "lnd":
            conf = LND_CONFIG_BASE
            conf += f" --bitcoind.rpcuser={self.tank.rpc_user}"
            conf += f" --bitcoind.rpcpass={self.tank.rpc_password}"
            conf += f" --bitcoind.rpchost={tank_container_name}:{self.tank.rpc_port}"
            conf += f" --bitcoind.zmqpubrawblock=tcp://{tank_container_name}:{self.tank.zmqblockport}"
            conf += f" --bitcoind.zmqpubrawtx=tcp://{tank_container_name}:{self.tank.zmqtxport}"
            conf += f" --rpclisten=0.0.0.0:{self.rpc_port}"
            conf += f" --alias={self.tank.index}"
            conf += f" --externalhosts={ln_container_name}"
            conf += f" --tlsextradomain={ln_container_name}"
            conf += " " + self.ln_config
            return conf
        return ""

    @exponential_backoff(max_retries=20, max_delay=300)
    @handle_json
    def lncli(self, cmd) -> dict:
        cmd = f"lncli --network=regtest {cmd}"
        return self.backend.exec_run(self.tank.index, ServiceType.LIGHTNING, cmd)

    def getnewaddress(self):
        res = self.lncli("newaddress p2wkh")
        return res["address"]

    def getURI(self):
        res = self.lncli("getinfo")
        return res["uris"][0]

    def get_wallet_balance(self):
        res = self.lncli("walletbalance")
        return res

    def open_channel_to_tank(self, index, amt):
        tank = self.warnet.tanks[index]
        [pubkey, host] = tank.lnnode.getURI().split("@")
        res = self.lncli(f"openchannel --node_key={pubkey} --connect={host} --local_amt={amt}")
        return res

    def connect_to_tank(self, index):
        tank = self.warnet.tanks[index]
        uri = tank.lnnode.getURI()
        res = self.lncli(f"connect {uri}")
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
        container_name = self.backend.get_container_name(self.tank.index, ServiceType.LIGHTNING)
        macaroon_filename = f"{container_name}_admin.macaroon"
        cert_filename = f"{container_name}_tls.cert"
        macaroon_path = os.path.join(subdir, macaroon_filename)
        cert_path = os.path.join(subdir, cert_filename)
        macaroon = self.backend.get_file(
            self.tank.index,
            ServiceType.LIGHTNING,
            "/root/.lnd/data/chain/bitcoin/regtest/admin.macaroon",
        )
        cert = self.backend.get_file(self.tank.index, ServiceType.LIGHTNING, "/root/.lnd/tls.cert")

        with open(macaroon_path, "wb") as f:
            f.write(macaroon)

        with open(cert_path, "wb") as f:
            f.write(cert)

        config["nodes"].append(
            {
                "id": container_name,
                "address": f"https://{self.ipv4}:{self.rpc_port}",
                "macaroon": macaroon_path,
                "cert": cert_path,
            }
        )
