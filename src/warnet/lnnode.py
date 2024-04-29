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
        ret = self.lncli(f"updatechanpolicy --chan_point={chan_point} {policy}")
        if len(ret["failed_updates"]) == 0:
            return ret
        else:
            raise Exception(ret)

    def get_graph_nodes(self) -> list[str]:
        if self.impl == "lnd":
            return list(n["pub_key"] for n in self.lncli("describegraph")["nodes"])
        elif self.impl == "cln":
            return list(n["nodeid"] for n in self.lncli("listnodes")["nodes"])
        raise Exception(f"Unsupported LN implementation: {self.impl}")

    def get_graph_channels(self) -> list[dict]:
        if self.impl == "lnd":
            edges = self.lncli("describegraph")["edges"]
            return list(
                map(
                    lambda edge: {"node1_pub": edge["node1_pub"], "node2_pub": edge["node2_pub"]},
                    edges,
                )
            )
        elif self.impl == "cln":
            channels = self.lncli("listchannels")["channels"]
            # CLN lists channels twice, once for each direction. This deduplicates them.
            channels = {chan["short_channel_id"]: chan for chan in channels}.values()
            return list(
                map(
                    lambda edge: {"node1_pub": edge["source"], "node2_pub": edge["destination"]},
                    channels,
                )
            )
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
