import argparse
import base64
import configparser
import json
import logging
import os
import pathlib
import random
import signal
import struct
import sys
import tempfile
import threading
from time import sleep

from kubernetes import client, config
from kubernetes.stream import stream
from ln_framework.ln import CLN, LND, LNNode
from test_framework.authproxy import AuthServiceProxy
from test_framework.blocktools import get_witness_script, script_BIP34_coinbase_height
from test_framework.messages import (
    CBlock,
    CBlockHeader,
    COutPoint,
    CTransaction,
    CTxIn,
    CTxInWitness,
    CTxOut,
    from_binary,
    from_hex,
    hash256,
    ser_string,
    ser_uint256,
    tx_from_hex,
)
from test_framework.p2p import MAGIC_BYTES, NetworkThread
from test_framework.psbt import (
    PSBT,
    PSBT_GLOBAL_UNSIGNED_TX,
    PSBT_IN_FINAL_SCRIPTSIG,
    PSBT_IN_FINAL_SCRIPTWITNESS,
    PSBT_IN_NON_WITNESS_UTXO,
    PSBT_IN_SIGHASH_TYPE,
    PSBTMap,
)
from test_framework.script import CScriptOp
from test_framework.test_framework import (
    TMPDIR_PREFIX,
    BitcoinTestFramework,
    TestStatus,
)
from test_framework.test_node import TestNode
from test_framework.util import PortSeed, get_rpc_proxy

SIGNET_HEADER = b"\xec\xc7\xda\xa2"
PSBT_SIGNET_BLOCK = (
    b"\xfc\x06signetb"  # proprietary PSBT global field holding the block being signed
)

NAMESPACE = None
pods = client.V1PodList(items=[])
cmaps = client.V1ConfigMapList(items=[])

try:
    # Get the in-cluster k8s client to determine what we have access to
    config.load_incluster_config()
    sclient = client.CoreV1Api()

    # Figure out what namespace we are in
    with open("/var/run/secrets/kubernetes.io/serviceaccount/namespace") as f:
        NAMESPACE = f.read().strip()

    try:
        # An admin with cluster access can list everything.
        # A wargames player with namespaced access will get a FORBIDDEN error here
        pods = sclient.list_pod_for_all_namespaces()
        cmaps = sclient.list_config_map_for_all_namespaces()
    except Exception:
        # Just get whatever we have access to in this namespace only
        pods = sclient.list_namespaced_pod(namespace=NAMESPACE)
        cmaps = sclient.list_namespaced_config_map(namespace=NAMESPACE)
except Exception:
    # If there is no cluster config, the user might just be
    # running the scenario file locally with --help
    pass

WARNET = {"tanks": [], "lightning": [], "channels": []}
for pod in pods.items:
    if "mission" not in pod.metadata.labels:
        continue

    if pod.metadata.labels["mission"] == "tank":
        WARNET["tanks"].append(
            {
                "tank": pod.metadata.name,
                "namespace": pod.metadata.namespace,
                "chain": pod.metadata.labels["chain"],
                "p2pport": int(pod.metadata.labels["P2PPort"]),
                "rpc_host": pod.status.pod_ip,
                "rpc_port": int(pod.metadata.labels["RPCPort"]),
                "rpc_user": "user",
                "rpc_password": pod.metadata.labels["rpcpassword"],
                "init_peers": pod.metadata.annotations["init_peers"],
            }
        )

    if pod.metadata.labels["mission"] == "lightning":
        if "lnd" in pod.metadata.labels["app.kubernetes.io/name"]:
            lnnode = LND(
                pod.metadata.name,
                pod.metadata.namespace,
                pod.status.pod_ip,
                pod.metadata.annotations["adminMacaroon"],
            )
        if "cln" in pod.metadata.labels["app.kubernetes.io/name"]:
            lnnode = CLN(pod.metadata.name, pod.metadata.namespace, pod.status.pod_ip)
        assert lnnode
        WARNET["lightning"].append(lnnode)

for cm in cmaps.items:
    if not cm.metadata.labels or "channels" not in cm.metadata.labels:
        continue
    channel_jsons = json.loads(cm.data["channels"])
    for channel_json in channel_jsons:
        channel_json["source"] = cm.data["source"]
        WARNET["channels"].append(channel_json)


# Ensure that all RPC calls are made with brand new http connections
def auth_proxy_request(self, method, path, postdata):
    self._set_conn()  # creates new http client connection
    return self.oldrequest(method, path, postdata)


AuthServiceProxy.oldrequest = AuthServiceProxy._request
AuthServiceProxy._request = auth_proxy_request


# Create a custom formatter
class ColorFormatter(logging.Formatter):
    """Custom formatter to add color based on log level."""

    # Define ANSI color codes
    RED = "\033[91m"
    YELLOW = "\033[93m"
    GREEN = "\033[92m"
    RESET = "\033[0m"

    FORMATS = {
        logging.DEBUG: f"{RESET}%(name)-8s - Thread-%(thread)d - %(message)s{RESET}",
        logging.INFO: f"{RESET}%(name)-8s - %(message)s{RESET}",
        logging.WARNING: f"{YELLOW}%(name)-8s - %(message)s{RESET}",
        logging.ERROR: f"{RED}%(name)-8s - %(message)s{RESET}",
        logging.CRITICAL: f"{RED}##%(name)-8s - %(message)s##{RESET}",
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


class Commander(BitcoinTestFramework):
    # required by subclasses of BitcoinTestFramework
    def set_test_params(self):
        pass

    def run_test(self):
        pass

    # Utility functions for Warnet scenarios
    @staticmethod
    def ensure_miner(node):
        wallets = node.listwallets()
        if "miner" not in wallets:
            node.createwallet("miner", descriptors=True)
        return node.get_wallet_rpc("miner")

    @staticmethod
    def hex_to_b64(hex):
        return base64.b64encode(bytes.fromhex(hex)).decode()

    @staticmethod
    def b64_to_hex(b64, reverse=False):
        if reverse:
            return base64.b64decode(b64)[::-1].hex()
        else:
            return base64.b64decode(b64).hex()

    def wait_for_tanks_connected(self):
        def tank_connected(self, tank):
            while True:
                peers = tank.getpeerinfo()
                count = sum(
                    1
                    for peer in peers
                    if peer.get("connection_type") == "manual" or peer.get("addnode") is True
                )
                self.log.info(f"Tank {tank.tank} connected to {count}/{tank.init_peers} peers")
                if count >= tank.init_peers:
                    break
                else:
                    sleep(5)

        conn_threads = [
            threading.Thread(target=tank_connected, args=(self, tank)) for tank in self.nodes
        ]
        for thread in conn_threads:
            thread.start()

        all(thread.join() is None for thread in conn_threads)
        self.log.info("Network connected")

    def handle_sigterm(self, signum, frame):
        print("SIGTERM received, stopping...")
        self.shutdown()
        sys.exit(0)

    # The following functions are chopped-up hacks of
    # the original methods from BitcoinTestFramework

    def setup(self):
        signal.signal(signal.SIGTERM, self.handle_sigterm)

        # hacked from _start_logging()
        # Scenarios will log plain messages to stdout only, which will can redirected by warnet
        self.log = logging.getLogger(self.__class__.__name__)
        self.log.setLevel(logging.INFO)  # set this to DEBUG to see ALL RPC CALLS

        # Because scenarios run in their own subprocess, the logger here
        # is not the same as the warnet server or other global loggers.
        # Scenarios log directly to stdout which gets picked up by the
        # subprocess manager in the server, and reprinted to the global log.
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(ColorFormatter())
        self.log.addHandler(ch)

        # Keep a separate index of tanks by pod name
        self.tanks: dict[str, TestNode] = {}
        self.lns: dict[str, LNNode] = {}
        self.channels = WARNET["channels"]

        for i, tank in enumerate(WARNET["tanks"]):
            self.log.info(
                f"Adding TestNode #{i} from pod {tank['tank']} with IP {tank['rpc_host']}"
            )
            node = TestNode(
                i,
                pathlib.Path(),  # datadir path
                chain=tank["chain"],
                rpchost=tank["rpc_host"],
                timewait=60,
                timeout_factor=self.options.timeout_factor,
                bitcoind=None,
                bitcoin_cli=None,
                cwd=self.options.tmpdir,
                coverage_dir=self.options.coveragedir,
            )
            node.tank = tank["tank"]
            node.rpc = get_rpc_proxy(
                f"http://{tank['rpc_user']}:{tank['rpc_password']}@{tank['rpc_host']}:{tank['rpc_port']}",
                i,
                timeout=60,
                coveragedir=self.options.coveragedir,
            )
            node.rpc_connected = True
            node.init_peers = int(tank["init_peers"])
            node.p2pport = tank["p2pport"]

            self.nodes.append(node)
            self.tanks[tank["tank"]] = node

        self.ln_nodes = []
        for ln in WARNET["lightning"]:
            self.ln_nodes.append(ln)
            self.lns[ln.name] = ln

        self.num_nodes = len(self.nodes)

        # Set up temp directory and start logging
        if self.options.tmpdir:
            self.options.tmpdir = os.path.abspath(self.options.tmpdir)
            os.makedirs(self.options.tmpdir, exist_ok=False)
        else:
            self.options.tmpdir = tempfile.mkdtemp(prefix=TMPDIR_PREFIX)

        seed = self.options.randomseed
        if seed is None:
            seed = random.randrange(sys.maxsize)
        else:
            self.log.info(f"User supplied random seed {seed}")
        random.seed(seed)
        self.log.info(f"PRNG seed is: {seed}")

        self.log.debug("Setting up network thread")
        self.network_thread = NetworkThread()
        self.network_thread.start()

        self.success = TestStatus.PASSED

        if len(self.nodes) > 0 and self.nodes[0].chain == "signet":
            # There's no garuntee that any nodes are responsive
            # but we only need one to figure out the network magic bytes
            for node in self.nodes:
                try:
                    # Times out after 60 seconds (!)
                    template = node.getblocktemplate({"rules": ["segwit", "signet"]})
                    challenge = template["signet_challenge"]
                    challenge_bytes = bytes.fromhex(challenge)
                    data = len(challenge_bytes).to_bytes() + challenge_bytes
                    digest = hash256(data)
                    MAGIC_BYTES["signet"] = digest[0:4]
                    self.log.info(
                        f"Got signet network magic bytes from {node.tank}: {MAGIC_BYTES['signet'].hex()}"
                    )
                    break
                except Exception as e:
                    self.log.info(f"Failed to get signet network magic bytes from {node.tank}: {e}")

    def parse_args(self):
        # Only print "outer" args from parent class when using --help
        help_parser = argparse.ArgumentParser(usage="%(prog)s [options]")
        self.add_options(help_parser)
        help_args, _ = help_parser.parse_known_args()
        # Check if 'help' attribute exists in help_args before accessing it
        if hasattr(help_args, "help") and help_args.help:
            help_parser.print_help()
            sys.exit(0)

        previous_releases_path = ""
        parser = argparse.ArgumentParser(usage="%(prog)s [options]")
        parser.add_argument(
            "--nocleanup",
            dest="nocleanup",
            default=False,
            action="store_true",
            help="Leave bitcoinds and test.* datadir on exit or error",
        )
        parser.add_argument(
            "--nosandbox",
            dest="nosandbox",
            default=False,
            action="store_true",
            help="Don't use the syscall sandbox",
        )
        parser.add_argument(
            "--noshutdown",
            dest="noshutdown",
            default=False,
            action="store_true",
            help="Don't stop bitcoinds after the test execution",
        )
        parser.add_argument(
            "--cachedir",
            dest="cachedir",
            default=None,
            help="Directory for caching pregenerated datadirs (default: %(default)s)",
        )
        parser.add_argument(
            "--tmpdir", dest="tmpdir", default=None, help="Root directory for datadirs"
        )
        parser.add_argument(
            "-l",
            "--loglevel",
            dest="loglevel",
            default="DEBUG",
            help="log events at this level and higher to the console. Can be set to DEBUG, INFO, WARNING, ERROR or CRITICAL. Passing --loglevel DEBUG will output all logs to console. Note that logs at all levels are always written to the test_framework.log file in the temporary test directory.",
        )
        parser.add_argument(
            "--tracerpc",
            dest="trace_rpc",
            default=False,
            action="store_true",
            help="Print out all RPC calls as they are made",
        )
        parser.add_argument(
            "--portseed",
            dest="port_seed",
            default=0,
            help="The seed to use for assigning port numbers (default: current process id)",
        )
        parser.add_argument(
            "--previous-releases",
            dest="prev_releases",
            default=None,
            action="store_true",
            help="Force test of previous releases (default: %(default)s)",
        )
        parser.add_argument(
            "--coveragedir",
            dest="coveragedir",
            default=None,
            help="Write tested RPC commands into this directory",
        )
        parser.add_argument(
            "--configfile",
            dest="configfile",
            default=None,
            help="Location of the test framework config file (default: %(default)s)",
        )
        parser.add_argument(
            "--pdbonfailure",
            dest="pdbonfailure",
            default=False,
            action="store_true",
            help="Attach a python debugger if test fails",
        )
        parser.add_argument(
            "--usecli",
            dest="usecli",
            default=False,
            action="store_true",
            help="use bitcoin-cli instead of RPC for all commands",
        )
        parser.add_argument(
            "--perf",
            dest="perf",
            default=False,
            action="store_true",
            help="profile running nodes with perf for the duration of the test",
        )
        parser.add_argument(
            "--valgrind",
            dest="valgrind",
            default=False,
            action="store_true",
            help="run nodes under the valgrind memory error detector: expect at least a ~10x slowdown. valgrind 3.14 or later required.",
        )
        parser.add_argument(
            "--randomseed",
            default=0x7761726E6574,  # "warnet" ascii
            help="set a random seed for deterministically reproducing a previous test run",
        )
        parser.add_argument(
            "--timeout-factor",
            dest="timeout_factor",
            default=1,
            help="adjust test timeouts by a factor. Setting it to 0 disables all timeouts",
        )
        parser.add_argument(
            "--network",
            dest="network",
            default="warnet",
            help="Designate which warnet this should run on (default: warnet)",
        )
        parser.add_argument(
            "--v2transport",
            dest="v2transport",
            default=False,
            action="store_true",
            help="use BIP324 v2 connections between all nodes by default",
        )

        self.add_options(parser)
        # Running TestShell in a Jupyter notebook causes an additional -f argument
        # To keep TestShell from failing with an "unrecognized argument" error, we add a dummy "-f" argument
        # source: https://stackoverflow.com/questions/48796169/how-to-fix-ipykernel-launcher-py-error-unrecognized-arguments-in-jupyter/56349168#56349168
        parser.add_argument("-f", "--fff", help="a dummy argument to fool ipython", default="1")
        self.options = parser.parse_args()
        if self.options.timeout_factor == 0:
            self.options.timeout_factor = 99999
        self.options.timeout_factor = self.options.timeout_factor or (
            4 if self.options.valgrind else 1
        )
        self.options.previous_releases_path = previous_releases_path
        config = configparser.ConfigParser()
        if self.options.configfile is not None:
            with open(self.options.configfile) as f:
                config.read_file(f)

        config["environment"] = {"PACKAGE_BUGREPORT": ""}

        self.config = config

        if "descriptors" not in self.options:
            # Wallet is not required by the test at all and the value of self.options.descriptors won't matter.
            # It still needs to exist and be None in order for tests to work however.
            # So set it to None to force -disablewallet, because the wallet is not needed.
            self.options.descriptors = None
        elif self.options.descriptors is None:
            # Some wallet is either required or optionally used by the test.
            # Prefer SQLite unless it isn't available
            if self.is_sqlite_compiled():
                self.options.descriptors = True
            elif self.is_bdb_compiled():
                self.options.descriptors = False
            else:
                # If neither are compiled, tests requiring a wallet will be skipped and the value of self.options.descriptors won't matter
                # It still needs to exist and be None in order for tests to work however.
                # So set it to None, which will also set -disablewallet.
                self.options.descriptors = None

        PortSeed.n = self.options.port_seed

    def connect_nodes(self, a, b, *, peer_advertises_v2=None, wait_for_connect: bool = True):
        """
        Kwargs:
            wait_for_connect: if True, block until the nodes are verified as connected. You might
                want to disable this when using -stopatheight with one of the connected nodes,
                since there will be a race between the actual connection and performing
                the assertions before one node shuts down.
        """
        from_connection = self.nodes[a]
        to_connection = self.nodes[b]
        from_num_peers = 1 + len(from_connection.getpeerinfo())
        to_num_peers = 1 + len(to_connection.getpeerinfo())
        ip_port = f"{self.nodes[b].rpchost}:{self.nodes[b].p2pport}"

        if peer_advertises_v2 is None:
            peer_advertises_v2 = self.options.v2transport

        if peer_advertises_v2:
            from_connection.addnode(node=ip_port, command="onetry", v2transport=True)
        else:
            # skip the optional third argument (default false) for
            # compatibility with older clients
            from_connection.addnode(ip_port, "onetry")

        if not wait_for_connect:
            return

        # poll until version handshake complete to avoid race conditions
        # with transaction relaying
        # See comments in net_processing:
        # * Must have a version message before anything else
        # * Must have a verack message before anything else
        self.wait_until(
            lambda: sum(peer["version"] != 0 for peer in from_connection.getpeerinfo())
            == from_num_peers
        )
        self.wait_until(
            lambda: sum(peer["version"] != 0 for peer in to_connection.getpeerinfo())
            == to_num_peers
        )
        self.wait_until(
            lambda: sum(
                peer["bytesrecv_per_msg"].pop("verack", 0) >= 21
                for peer in from_connection.getpeerinfo()
            )
            == from_num_peers
        )
        self.wait_until(
            lambda: sum(
                peer["bytesrecv_per_msg"].pop("verack", 0) >= 21
                for peer in to_connection.getpeerinfo()
            )
            == to_num_peers
        )
        # The message bytes are counted before processing the message, so make
        # sure it was fully processed by waiting for a ping.
        self.wait_until(
            lambda: sum(
                peer["bytesrecv_per_msg"].pop("pong", 0) >= 29
                for peer in from_connection.getpeerinfo()
            )
            == from_num_peers
        )
        self.wait_until(
            lambda: sum(
                peer["bytesrecv_per_msg"].pop("pong", 0) >= 29
                for peer in to_connection.getpeerinfo()
            )
            == to_num_peers
        )

    def generatetoaddress(self, generator, n, addr, sync_fun=None, **kwargs):
        if generator.chain == "regtest":
            blocks = generator.generatetoaddress(n, addr, invalid_call=False, **kwargs)
            sync_fun() if sync_fun else self.sync_all()
            return blocks
        if generator.chain == "signet":
            mined_blocks = 0
            block_hashes = []

            def bcli(method, *args, **kwargs):
                return generator.__getattr__(method)(*args, **kwargs)

            while mined_blocks < n:
                # gbt
                tmpl = bcli("getblocktemplate", {"rules": ["signet", "segwit"]})
                # address for reward
                reward_spk = bytes.fromhex(bcli("getaddressinfo", addr)["scriptPubKey"])
                # create coinbase tx
                cbtx = CTransaction()
                cbtx.vin = [
                    CTxIn(
                        COutPoint(0, 0xFFFFFFFF),
                        script_BIP34_coinbase_height(tmpl["height"]),
                        0xFFFFFFFF,
                    )
                ]
                cbtx.vout = [CTxOut(tmpl["coinbasevalue"], reward_spk)]
                cbtx.vin[0].nSequence = 2**32 - 2
                cbtx.rehash()
                # assemble block
                block = CBlock()
                block.nVersion = tmpl["version"]
                block.hashPrevBlock = int(tmpl["previousblockhash"], 16)
                block.nTime = tmpl["curtime"]
                if block.nTime < tmpl["mintime"]:
                    block.nTime = tmpl["mintime"]
                block.nBits = int(tmpl["bits"], 16)
                block.nNonce = 0
                block.vtx = [cbtx] + [tx_from_hex(t["data"]) for t in tmpl["transactions"]]
                witnonce = 0
                witroot = block.calc_witness_merkle_root()
                cbwit = CTxInWitness()
                cbwit.scriptWitness.stack = [ser_uint256(witnonce)]
                block.vtx[0].wit.vtxinwit = [cbwit]
                block.vtx[0].vout.append(CTxOut(0, bytes(get_witness_script(witroot, witnonce))))
                # create signet txs for signing
                signet_spk = tmpl["signet_challenge"]
                signet_spk_bin = bytes.fromhex(signet_spk)
                txs = block.vtx[:]
                txs[0] = CTransaction(txs[0])
                txs[0].vout[-1].scriptPubKey += CScriptOp.encode_op_pushdata(SIGNET_HEADER)
                hashes = []
                for tx in txs:
                    tx.rehash()
                    hashes.append(ser_uint256(tx.sha256))
                mroot = block.get_merkle_root(hashes)
                sd = b""
                sd += struct.pack("<i", block.nVersion)
                sd += ser_uint256(block.hashPrevBlock)
                sd += ser_uint256(mroot)
                sd += struct.pack("<I", block.nTime)
                to_spend = CTransaction()
                to_spend.nVersion = 0
                to_spend.nLockTime = 0
                to_spend.vin = [
                    CTxIn(COutPoint(0, 0xFFFFFFFF), b"\x00" + CScriptOp.encode_op_pushdata(sd), 0)
                ]
                to_spend.vout = [CTxOut(0, signet_spk_bin)]
                to_spend.rehash()
                spend = CTransaction()
                spend.nVersion = 0
                spend.nLockTime = 0
                spend.vin = [CTxIn(COutPoint(to_spend.sha256, 0), b"", 0)]
                spend.vout = [CTxOut(0, b"\x6a")]
                # create PSBT for miner wallet signing
                psbt = PSBT()
                psbt.g = PSBTMap(
                    {
                        PSBT_GLOBAL_UNSIGNED_TX: spend.serialize(),
                        PSBT_SIGNET_BLOCK: block.serialize(),
                    }
                )
                psbt.i = [
                    PSBTMap(
                        {
                            PSBT_IN_NON_WITNESS_UTXO: to_spend.serialize(),
                            PSBT_IN_SIGHASH_TYPE: bytes([1, 0, 0, 0]),
                        }
                    )
                ]
                psbt.o = [PSBTMap()]
                psbt = psbt.to_base64()
                # sign PSBT
                psbt_signed = bcli("walletprocesspsbt", psbt=psbt, sign=True, sighashtype="ALL")
                if not psbt_signed.get("complete", False):
                    self.log.error("PSBT signing failed, aborting...")
                    return block_hashes
                # decode signed PSBT
                signed_psbt = PSBT.from_base64(psbt_signed["psbt"])
                scriptSig = signed_psbt.i[0].map.get(PSBT_IN_FINAL_SCRIPTSIG, b"")
                scriptWitness = signed_psbt.i[0].map.get(PSBT_IN_FINAL_SCRIPTWITNESS, b"\x00")
                signed_block = from_binary(CBlock, signed_psbt.g.map[PSBT_SIGNET_BLOCK])
                signet_solution = ser_string(scriptSig) + scriptWitness
                # finish block
                signed_block.vtx[0].vout[-1].scriptPubKey += CScriptOp.encode_op_pushdata(
                    SIGNET_HEADER + signet_solution
                )
                signed_block.vtx[0].rehash()
                signed_block.hashMerkleRoot = signed_block.calc_merkle_root()
                try:
                    headhex = CBlockHeader.serialize(signed_block).hex()
                    cmd = ["bitcoin-util", "grind", headhex]
                    newheadhex = stream(
                        sclient.connect_get_namespaced_pod_exec,
                        name=generator.tank,
                        container="bitcoincore",
                        namespace=NAMESPACE,
                        command=cmd,
                        stderr=True,
                        stdin=False,
                        stdout=True,
                        tty=False,
                    )
                    if "not found" in newheadhex:
                        raise Exception(newheadhex)
                    newhead = from_hex(CBlockHeader(), newheadhex.strip())
                    signed_block.nNonce = newhead.nNonce
                    signed_block.rehash()
                except Exception as e:
                    self.log.info(
                        f"Error grinding signet PoW with bitcoin-util in {generator.tank}: {e}".strip()
                    )
                    self.log.info("  re-attempting with a single python thread...")
                    signed_block.solve()
                # submit block
                bcli("submitblock", signed_block.serialize().hex())
                block_hashes.append(signed_block.hash)
                mined_blocks += 1
                self.log.info(f"Generated {mined_blocks} signet blocks")

            return block_hashes
