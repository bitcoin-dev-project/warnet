import argparse
import configparser
import json
import logging
import os
import pathlib
import random
import signal
import sys
import tempfile
from pathlib import Path

from test_framework.authproxy import AuthServiceProxy
from test_framework.p2p import NetworkThread
from test_framework.test_framework import (
    TMPDIR_PREFIX,
    BitcoinTestFramework,
    TestStatus,
)
from test_framework.test_node import TestNode
from test_framework.util import PortSeed, get_rpc_proxy

WARNET_FILE = Path(os.path.dirname(__file__)) / "warnet.json"

try:
    with open(WARNET_FILE) as file:
        WARNET = json.load(file)
except Exception:
    WARNET = []


# Ensure that all RPC calls are made with brand new http connections
def auth_proxy_request(self, method, path, postdata):
    self._set_conn()  # creates new http client connection
    return self.oldrequest(method, path, postdata)


AuthServiceProxy.oldrequest = AuthServiceProxy._request
AuthServiceProxy._request = auth_proxy_request


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
        formatter = logging.Formatter(fmt="%(name)-8s %(message)s")
        ch.setFormatter(formatter)
        self.log.addHandler(ch)

        for i, tank in enumerate(WARNET):
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
            node.init_peers = tank["init_peers"]
            self.nodes.append(node)

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
        ip_port = self.nodes[b].rpchost + ":18444"

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
