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

CLN_CONFIG_BASE = " ".join(
    [
        "--network=regtest",
        "--database-upgrade=true",
        "--bitcoin-retry-timeout=600",
        "--bind-addr=0.0.0.0:9735",
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
        elif self.impl == "cln":
            conf = CLN_CONFIG_BASE
            conf += f" --alias={self.tank.index}"
            conf += f" --grpc-port={self.rpc_port}"
            conf += f" --bitcoin-rpcuser={self.tank.rpc_user}"
            conf += f" --bitcoin-rpcpassword={self.tank.rpc_password}"
            conf += f" --bitcoin-rpcconnect={tank_container_name}"
            conf += f" --bitcoin-rpcport={self.tank.rpc_port}"
            conf += f" --announce-addr=dns:{ln_container_name}:9735"
            return conf
        return ""

    @exponential_backoff(max_retries=20, max_delay=300)
    @handle_json
    def lncli(self, cmd) -> dict:
        cli = ""
        if self.impl == "lnd":
            cli = "lncli"
        elif self.impl == "cln":
            cli = "lightning-cli"
        else:
            raise Exception(f"Unsupported LN implementation: {self.impl}")
        cmd = f"{cli} --network=regtest {cmd}"
        return self.backend.exec_run(self.tank.index, ServiceType.LIGHTNING, cmd)

    def getnewaddress(self):
        if self.impl == "lnd":
            return self.lncli("newaddress p2wkh")["address"]
        elif self.impl == "cln":
            return self.lncli("newaddr")["bech32"]
        raise Exception(f"Unsupported LN implementation: {self.impl}")

    def get_pub_key(self):
        res = self.lncli("getinfo")
        if self.impl == "lnd":
            return res["identity_pubkey"]
        elif self.impl == "cln":
            return res["id"]
        raise Exception(f"Unsupported LN implementation: {self.impl}")

    def getURI(self):
        res = self.lncli("getinfo")
        if self.impl == "lnd":
            if len(res["uris"]) < 1:
                return None
            return res["uris"][0]
        elif self.impl == "cln":
            if len(res["address"]) < 1:
                return None
            return f'{res["id"]}@{res["address"][0]["address"]}:{res["address"][0]["port"]}'
        raise Exception(f"Unsupported LN implementation: {self.impl}")

    def get_wallet_balance(self) -> int:
        if self.impl == "lnd":
            res = self.lncli("walletbalance")["confirmed_balance"]
            return res
        elif self.impl == "cln":
            res = self.lncli("listfunds")
            return int(sum(o["amount_msat"] for o in res["outputs"]) / 1000)
        raise Exception(f"Unsupported LN implementation: {self.impl}")

    # returns the channel point in the form txid:output_index
    def open_channel_to_tank(self, index: int, channel_open_data: str) -> str:
        tank = self.warnet.tanks[index]
        [pubkey, host] = tank.lnnode.getURI().split("@")
        if self.impl == "lnd":
            txid = self.lncli(
                f"openchannel --node_key={pubkey} --connect={host} {channel_open_data}"
            )["funding_txid"]
            # Why doesn't LND return the output index as well?
            # Do they charge by the RPC call or something?!
            pending = self.lncli("pendingchannels")
            for chan in pending["pending_open_channels"]:
                if txid in chan["channel"]["channel_point"]:
                    return chan["channel"]["channel_point"]
            raise Exception(f"Opened channel with txid {txid} not found in pending channels")
        if self.impl == "cln":
            res = self.lncli(f"fundchannel id={pubkey} {channel_open_data}")
            return f"{res['txid']}:{res['outnum']}"
        raise Exception(f"Unsupported LN implementation: {self.impl}")

    def update_channel_policy(self, chan_point: str, policy: str) -> str:
        if self.impl == "lnd":
            ret = self.lncli(f"updatechanpolicy --chan_point={chan_point} {policy}")
            if len(ret["failed_updates"]) == 0:
                return ret
            else:
                raise Exception(ret)
        elif self.impl == "cln":
            return self.lncli(f"setchannel {chan_point} {policy}")
        raise Exception(f"Unsupported LN implementation: {self.impl}")

    def get_graph_nodes(self) -> list[str]:
        if self.impl == "lnd":
            return list(n["pub_key"] for n in self.lncli("describegraph")["nodes"])
        elif self.impl == "cln":
            return list(n["nodeid"] for n in self.lncli("listnodes")["nodes"])
        raise Exception(f"Unsupported LN implementation: {self.impl}")

    def get_graph_channels(self) -> list[dict]:
        if self.impl == "lnd":
            edges = self.lncli("describegraph")["edges"]
            return [
                LNChannel(
                    node1_pub=edge["node1_pub"],
                    node2_pub=edge["node2_pub"],
                    capacity_msat=edge["capacity"],
                    short_chan_id=lnd_to_cl_scid(edge["channel_id"]),
                    node1_min_htlc=edge["node1_policy"]["min_htlc"],
                    node2_min_htlc=edge["node2_policy"]["min_htlc"],
                    node1_max_htlc=edge["node1_policy"]["max_htlc"],
                    node2_max_htlc=edge["node2_policy"]["max_htlc"],
                    node1_base_fee_msat=edge["node1_policy"]["fee_base_msat"],
                    node2_base_fee_msat=edge["node2_policy"]["fee_base_msat"],
                    node1_fee_rate_milli_msat=edge["node1_policy"]["fee_rate_milli_msat"],
                    node2_fee_rate_milli_msat=edge["node2_policy"]["fee_rate_milli_msat"],
                    node1_time_lock_delta=edge["node1_policy"]["time_lock_delta"],
                    node2_time_lock_delta=edge["node2_policy"]["time_lock_delta"],
                )
                for edge in edges
            ]
        elif self.impl == "cln":
            cln_channels = self.lncli("listchannels")["channels"]
            # CLN lists channels twice, once for each direction. This finds the unique channel ids.
            short_channel_ids = {chan["short_channel_id"]: chan for chan in cln_channels}.keys()
            channels: list[LNChannel] = []
            for short_channel_id in short_channel_ids:
                channel_1 = channels[short_channel_id][0]
                channel_2 = channels[short_channel_id][1]

                channels.append(
                    LNChannel(
                        node1_pub=channel_1["source"],
                        node2_pub=channel_2["source"],
                        capacity_msat=channel_1["amount_msat"],
                        short_chan_id=channel_1["channel_id"],
                        node1_min_htlc=channel_1["htlc_minimum_msat"],
                        node2_min_htlc=channel_2["htlc_minimum_msat"],
                        node1_max_htlc=channel_1["htlc_maximum_msat"],
                        node2_max_htlc=channel_2["htlc_maximum_msat"],
                        node1_base_fee_msat=channel_1["base_fee_millisatoshi"],
                        node2_base_fee_msat=channel_2["base_fee_millisatoshi"],
                        node1_fee_rate_milli_msat=channel_1["fee_per_millionth"],
                        node2_fee_rate_milli_msat=channel_2["fee_per_millionth"],
                    )
                )

            return channels
        raise Exception(f"Unsupported LN implementation: {self.impl}")

    def get_peers(self) -> list[str]:
        if self.impl == "lnd":
            return list(p["pub_key"] for p in self.lncli("listpeers")["peers"])
        elif self.impl == "cln":
            return list(p["id"] for p in self.lncli("listpeers")["peers"])
        raise Exception(f"Unsupported LN implementation: {self.impl}")

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


class LNChannel:
    def __init__(
        self,
        node1_pub: str,
        node2_pub: str,
        capacity_msat: int = 0,
        short_chan_id: str = "",
        node1_min_htlc: int = 0,
        node2_min_htlc: int = 0,
        node1_max_htlc: int = 0,
        node2_max_htlc: int = 0,
        node1_base_fee_msat: int = 0,
        node2_base_fee_msat: int = 0,
        node1_fee_rate_milli_msat: int = 0,
        node2_fee_rate_milli_msat: int = 0,
        node1_time_lock_delta: int = 0,
        node2_time_lock_delta: int = 0,
    ) -> None:
        # Ensure that the node with the lower pubkey is node1
        if node1_pub > node2_pub:
            node1_pub, node2_pub = node2_pub, node1_pub
            node1_min_htlc, node2_min_htlc = node2_min_htlc, node1_min_htlc
            node1_max_htlc, node2_max_htlc = node2_max_htlc, node1_max_htlc
            node1_base_fee_msat, node2_base_fee_msat = node2_base_fee_msat, node1_base_fee_msat
            node1_fee_rate_milli_msat, node2_fee_rate_milli_msat = (
                node2_fee_rate_milli_msat,
                node1_fee_rate_milli_msat,
            )
            node1_time_lock_delta, node2_time_lock_delta = (
                node2_time_lock_delta,
                node1_time_lock_delta,
            )
        self.node1_pub = node1_pub
        self.node2_pub = node2_pub
        self.capacity_msat = capacity_msat
        self.short_chan_id = short_chan_id
        self.node1_min_htlc = node1_min_htlc
        self.node2_min_htlc = node2_min_htlc
        self.node1_max_htlc = node1_max_htlc
        self.node2_max_htlc = node2_max_htlc
        self.node1_base_fee_msat = node1_base_fee_msat
        self.node2_base_fee_msat = node2_base_fee_msat
        self.node1_fee_rate_milli_msat = node1_fee_rate_milli_msat
        self.node2_fee_rate_milli_msat = node2_fee_rate_milli_msat
        self.node1_time_lock_delta = node1_time_lock_delta
        self.node2_time_lock_delta = node2_time_lock_delta


def lnd_to_cl_scid(s) -> str:
    block = s >> 40
    tx = s >> 16 & 0xFFFFFF
    output = s & 0xFFFF
    return f"{block}x{tx}x{output}"


def cl_to_lnd_scid(s) -> int:
    s = [int(i) for i in s.split("x")]
    return (s[0] << 40) | (s[1] << 16) | s[2]
