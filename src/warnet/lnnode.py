import io
import tarfile

from backend.kubernetes_backend import KubernetesBackend
from warnet.services import ServiceType
from warnet.utils import exponential_backoff, generate_ipv4_addr, handle_json

from .status import RunningStatus

LND_CONFIG_BASE = " ".join(
    [
        "--noseedbackup",
        "--norest",
        "--debuglevel=debug",
        "--accept-keysend",
        "--bitcoin.active",
        "--bitcoin.regtest",
        "--bitcoin.node=bitcoind",
        "--maxpendingchannels=64",
        "--trickledelay=1",
    ]
)


class LNNode:
    def __init__(self, warnet, tank, backend: KubernetesBackend, options):
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
            conf += (
                f" --bitcoind.zmqpubrawblock=tcp://{tank_container_name}:{self.tank.zmqblockport}"
            )
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
        if len(res["uris"]) < 1:
            return None
        return res["uris"][0]

    def get_wallet_balance(self):
        res = self.lncli("walletbalance")
        return res

    # returns the channel point in the form txid:output_index
    def open_channel_to_tank(self, index: int, policy: str) -> str:
        tank = self.warnet.tanks[index]
        [pubkey, host] = tank.lnnode.getURI().split("@")
        txid = self.lncli(f"openchannel --node_key={pubkey} --connect={host} {policy}")[
            "funding_txid"
        ]
        # Why doesn't LND return the output index as well?
        # Do they charge by the RPC call or something?!
        pending = self.lncli("pendingchannels")
        for chan in pending["pending_open_channels"]:
            if txid in chan["channel"]["channel_point"]:
                return chan["channel"]["channel_point"]
        raise Exception(f"Opened channel with txid {txid} not found in pending channels")

    def update_channel_policy(self, chan_point: str, policy: str) -> str:
        ret = self.lncli(f"updatechanpolicy --chan_point={chan_point} {policy}")
        if len(ret["failed_updates"]) == 0:
            return ret
        else:
            raise Exception(ret)

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

    def export(self, config: object, tar_file):
        # Retrieve the credentials
        macaroon = self.backend.get_file(
            self.tank.index,
            ServiceType.LIGHTNING,
            "/root/.lnd/data/chain/bitcoin/regtest/admin.macaroon",
        )
        cert = self.backend.get_file(self.tank.index, ServiceType.LIGHTNING, "/root/.lnd/tls.cert")
        name = f"ln-{self.tank.index}"
        macaroon_filename = f"{name}_admin.macaroon"
        cert_filename = f"{name}_tls.cert"
        host = self.backend.get_lnnode_hostname(self.tank.index)

        # Add the files to the in-memory tar archive
        tarinfo1 = tarfile.TarInfo(name=macaroon_filename)
        tarinfo1.size = len(macaroon)
        fileobj1 = io.BytesIO(macaroon)
        tar_file.addfile(tarinfo=tarinfo1, fileobj=fileobj1)
        tarinfo2 = tarfile.TarInfo(name=cert_filename)
        tarinfo2.size = len(cert)
        fileobj2 = io.BytesIO(cert)
        tar_file.addfile(tarinfo=tarinfo2, fileobj=fileobj2)

        config["nodes"].append(
            {
                "id": name,
                "address": f"https://{host}:{self.rpc_port}",
                "macaroon": f"/simln/{macaroon_filename}",
                "cert": f"/simln/{cert_filename}",
            }
        )
