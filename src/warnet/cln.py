import io
import tarfile

from warnet.backend.kubernetes_backend import KubernetesBackend
from warnet.services import ServiceType
from warnet.utils import exponential_backoff, generate_ipv4_addr, handle_json

from .lnchannel import LNChannel, LNPolicy
from .lnnode import LNNode
from .status import RunningStatus

CLN_CONFIG_BASE = " ".join(
    [
        "--network=regtest",
        "--database-upgrade=true",
        "--bitcoin-retry-timeout=600",
        "--bind-addr=0.0.0.0:9735",
        "--developer",
        "--dev-fast-gossip",
        "--log-level=debug",
    ]
)


class CLNNode(LNNode):
    def __init__(self, warnet, tank, backend: KubernetesBackend, options):
        self.warnet = warnet
        self.tank = tank
        self.backend = backend
        self.image = options["ln_image"]
        self.cb = options["cb_image"]
        self.ln_config = options["ln_config"]
        self.ipv4 = generate_ipv4_addr(self.warnet.subnet)
        self.rpc_port = 10009
        self.impl = "cln"

    @property
    def status(self) -> RunningStatus:
        return super().status

    @property
    def cb_status(self) -> RunningStatus:
        return super().cb_status

    def get_conf(self, ln_container_name, tank_container_name) -> str:
        conf = CLN_CONFIG_BASE
        conf += f" --alias={self.tank.index}"
        conf += f" --grpc-port={self.rpc_port}"
        conf += f" --bitcoin-rpcuser={self.tank.rpc_user}"
        conf += f" --bitcoin-rpcpassword={self.tank.rpc_password}"
        conf += f" --bitcoin-rpcconnect={tank_container_name}"
        conf += f" --bitcoin-rpcport={self.tank.rpc_port}"
        conf += f" --announce-addr=dns:{ln_container_name}:9735"
        return conf

    @exponential_backoff(max_retries=20, max_delay=300)
    @handle_json
    def lncli(self, cmd) -> dict:
        cli = "lightning-cli"
        cmd = f"{cli} --network=regtest {cmd}"
        return self.backend.exec_run(self.tank.index, ServiceType.LIGHTNING, cmd)

    def getnewaddress(self):
        return self.lncli("newaddr")["bech32"]

    def get_pub_key(self):
        res = self.lncli("getinfo")
        return res["id"]

    def getURI(self):
        res = self.lncli("getinfo")
        if len(res["address"]) < 1:
            return None
        return f'{res["id"]}@{res["address"][0]["address"]}:{res["address"][0]["port"]}'

    def get_wallet_balance(self) -> int:
        res = self.lncli("listfunds")
        return int(sum(o["amount_msat"] for o in res["outputs"]) / 1000)

    # returns the channel point in the form txid:output_index
    def open_channel_to_tank(self, index: int, channel_open_data: str) -> str:
        tank = self.warnet.tanks[index]
        [pubkey, host] = tank.lnnode.getURI().split("@")
        res = self.lncli(f"fundchannel id={pubkey} {channel_open_data}")
        return f"{res['txid']}:{res['outnum']}"

    def update_channel_policy(self, chan_point: str, policy: str) -> str:
        return self.lncli(f"setchannel {chan_point} {policy}")

    def get_graph_nodes(self) -> list[str]:
        return list(n["nodeid"] for n in self.lncli("listnodes")["nodes"])

    def get_graph_channels(self) -> list[LNChannel]:
        cln_channels = self.lncli("listchannels")["channels"]
        # CLN lists channels twice, once for each direction. This finds the unique channel ids.
        short_channel_ids = {chan["short_channel_id"]: chan for chan in cln_channels}.keys()
        channels = []
        for short_channel_id in short_channel_ids:
            nodes = [
                chans for chans in cln_channels if chans["short_channel_id"] == short_channel_id
            ]
            # CLN has only heard about one side of the channel
            if len(nodes) == 1:
                channels.append(self.lnchannel_from_json(nodes[0], None))
                continue
            channels.append(self.lnchannel_from_json(nodes[0], nodes[1]))
        return channels

    @staticmethod
    def lnchannel_from_json(node1: object, node2: object) -> LNChannel:
        if not node1:
            raise ValueError("node1 can't be None")

        node2_policy = (
            LNPolicy(
                min_htlc=node2["htlc_minimum_msat"],
                max_htlc=node2["htlc_maximum_msat"],
                base_fee_msat=node2["base_fee_millisatoshi"],
                fee_rate_milli_msat=node2["fee_per_millionth"],
            )
            if node2 is not None
            else None
        )

        return LNChannel(
            node1_pub=node1["source"],
            node2_pub=node1["destination"],
            capacity_msat=node1["amount_msat"],
            short_chan_id=node1["short_channel_id"],
            node1_policy=LNPolicy(
                min_htlc=node1["htlc_minimum_msat"],
                max_htlc=node1["htlc_maximum_msat"],
                base_fee_msat=node1["base_fee_millisatoshi"],
                fee_rate_milli_msat=node1["fee_per_millionth"],
            ),
            node2_policy=node2_policy,
        )

    def get_peers(self) -> list[str]:
        return list(p["id"] for p in self.lncli("listpeers")["peers"])

    def connect_to_tank(self, index):
        return super().connect_to_tank(index)

    def generate_cli_command(self, command: list[str]):
        network = f"--network={self.tank.warnet.bitcoin_network}"
        cmd = f"{network} {' '.join(command)}"
        cmd = f"lightning-cli {cmd}"
        return cmd

    def export(self, config: object, tar_file):
        # Retrieve the credentials
        ca_cert = self.backend.get_file(
            self.tank.index,
            ServiceType.LIGHTNING,
            "/root/.lightning/regtest/ca.pem",
        )
        client_cert = self.backend.get_file(
            self.tank.index,
            ServiceType.LIGHTNING,
            "/root/.lightning/regtest/client.pem",
        )
        client_key = self.backend.get_file(
            self.tank.index,
            ServiceType.LIGHTNING,
            "/root/.lightning/regtest/client-key.pem",
        )
        name = f"ln-{self.tank.index}"
        ca_cert_filename = f"{name}_ca_cert.pem"
        client_cert_filename = f"{name}_client_cert.pem"
        client_key_filename = f"{name}_client_key.pem"
        host = self.backend.get_lnnode_hostname(self.tank.index)

        # Add the files to the in-memory tar archive
        tarinfo1 = tarfile.TarInfo(name=ca_cert_filename)
        tarinfo1.size = len(ca_cert)
        fileobj1 = io.BytesIO(ca_cert)
        tar_file.addfile(tarinfo=tarinfo1, fileobj=fileobj1)
        tarinfo2 = tarfile.TarInfo(name=client_cert_filename)
        tarinfo2.size = len(client_cert)
        fileobj2 = io.BytesIO(client_cert)
        tar_file.addfile(tarinfo=tarinfo2, fileobj=fileobj2)
        tarinfo3 = tarfile.TarInfo(name=client_key_filename)
        tarinfo3.size = len(client_key)
        fileobj3 = io.BytesIO(client_key)
        tar_file.addfile(tarinfo=tarinfo3, fileobj=fileobj3)

        config["nodes"].append(
            {
                "id": name,
                "address": f"https://{host}:{self.rpc_port}",
                "ca_cert": f"/simln/{ca_cert_filename}",
                "client_cert": f"/simln/{client_cert_filename}",
                "client_key": f"/simln/{client_key_filename}",
            }
        )
