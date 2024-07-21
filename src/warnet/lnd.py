import io
import tarfile

from warnet.backend.kubernetes_backend import KubernetesBackend
from warnet.services import ServiceType
from warnet.utils import exponential_backoff, generate_ipv4_addr, handle_json

from .lnchannel import LNChannel, LNPolicy
from .lnnode import LNNode, lnd_to_cl_scid
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


class LNDNode(LNNode):
    def __init__(self, warnet, tank, backend: KubernetesBackend, options):
        self.warnet = warnet
        self.tank = tank
        self.backend = backend
        self.image = options["ln_image"]
        self.cb = options["cb_image"]
        self.ln_config = options["ln_config"]
        self.ipv4 = generate_ipv4_addr(self.warnet.subnet)
        self.rpc_port = 10009
        self.impl = "lnd"

    @property
    def status(self) -> RunningStatus:
        return super().status

    @property
    def cb_status(self) -> RunningStatus:
        return super().cb_status

    def get_conf(self, ln_container_name, tank_container_name) -> str:
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

    @exponential_backoff(max_retries=20, max_delay=300)
    @handle_json
    def lncli(self, cmd) -> dict:
        cli = "lncli"
        cmd = f"{cli} --network=regtest {cmd}"
        return self.backend.exec_run(self.tank.index, ServiceType.LIGHTNING, cmd)

    def getnewaddress(self):
        return self.lncli("newaddress p2wkh")["address"]

    def get_pub_key(self):
        res = self.lncli("getinfo")
        return res["identity_pubkey"]

    def getURI(self):
        res = self.lncli("getinfo")
        if len(res["uris"]) < 1:
            return None
        return res["uris"][0]

    def get_wallet_balance(self) -> int:
        res = self.lncli("walletbalance")["confirmed_balance"]
        return res

    # returns the channel point in the form txid:output_index
    def open_channel_to_tank(self, index: int, channel_open_data: str) -> str:
        tank = self.warnet.tanks[index]
        [pubkey, host] = tank.lnnode.getURI().split("@")
        txid = self.lncli(f"openchannel --node_key={pubkey} --connect={host} {channel_open_data}")[
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

    def get_graph_nodes(self) -> list[str]:
        return list(n["pub_key"] for n in self.lncli("describegraph")["nodes"])

    def get_graph_channels(self) -> list[LNChannel]:
        edges = self.lncli("describegraph")["edges"]
        return [self.lnchannel_from_json(edge) for edge in edges]

    @staticmethod
    def lnchannel_from_json(edge: object) -> LNChannel:
        node1_policy = (
            LNPolicy(
                min_htlc=int(edge["node1_policy"]["min_htlc"]),
                max_htlc=int(edge["node1_policy"]["max_htlc_msat"]),
                base_fee_msat=int(edge["node1_policy"]["fee_base_msat"]),
                fee_rate_milli_msat=int(edge["node1_policy"]["fee_rate_milli_msat"]),
                time_lock_delta=int(edge["node1_policy"]["time_lock_delta"]),
            )
            if edge["node1_policy"]
            else None
        )

        node2_policy = (
            LNPolicy(
                min_htlc=int(edge["node2_policy"]["min_htlc"]),
                max_htlc=int(edge["node2_policy"]["max_htlc_msat"]),
                base_fee_msat=int(edge["node2_policy"]["fee_base_msat"]),
                fee_rate_milli_msat=int(edge["node2_policy"]["fee_rate_milli_msat"]),
                time_lock_delta=int(edge["node2_policy"]["time_lock_delta"]),
            )
            if edge["node2_policy"]
            else None
        )

        return LNChannel(
            node1_pub=edge["node1_pub"],
            node2_pub=edge["node2_pub"],
            capacity_msat=(int(edge["capacity"]) * 1000),
            short_chan_id=lnd_to_cl_scid(edge["channel_id"]),
            node1_policy=node1_policy,
            node2_policy=node2_policy,
        )

    def get_peers(self) -> list[str]:
        return list(p["pub_key"] for p in self.lncli("listpeers")["peers"])

    def connect_to_tank(self, index):
        return super().connect_to_tank(index)

    def generate_cli_command(self, command: list[str]):
        network = f"--network={self.tank.warnet.bitcoin_network}"
        cmd = f"{network} {' '.join(command)}"
        cmd = f"lncli {cmd}"
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
