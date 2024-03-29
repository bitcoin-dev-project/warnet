import argparse
import atexit
import os
import shlex
import sys
import threading
from pathlib import Path
from subprocess import PIPE, STDOUT, Popen, run
from tempfile import mkdtemp
from time import sleep

from cli.rpc import rpc_call
from warnet.utils import exponential_backoff
from warnet.warnet import Warnet

parser = argparse.ArgumentParser(description="TestBase args")
parser.add_argument("--backend", type=str, default="compose", help="Use compose or k8s backend")
parser.add_argument("--rust_cli", action="store_true", help="Use experimental Rust CLI")
args = parser.parse_args()


class TestBase:
    def __init__(self):
        # Warnet server stdout gets logged here
        self.tmpdir = Path(mkdtemp(prefix="warnet-test-"))

        os.environ["XDG_STATE_HOME"] = f"{self.tmpdir}"

        self.logfilepath = self.tmpdir / "warnet" / "warnet.log"

        # Use the same dir name for the warnet network name
        # but sanitize hyphens which make docker frown :-(
        self.network_name = self.tmpdir.name.replace("-", "")
        # also replace underscores which throws off k8s
        self.network_name = self.tmpdir.name.replace("_", "")

        self.server = None
        self.server_thread = None
        self.stop_threads = threading.Event()
        self.network = True
        self.rust_cli = args.rust_cli

        atexit.register(self.cleanup)

        self.backend = args.backend
        if self.backend not in ["compose", "k8s"]:
            print(f"Invalid backend {self.backend}")
            sys.exit(1)

        print("\nWarnet test base started")

    def cleanup(self, signum=None, frame=None):
        if self.server is None:
            return

        try:
            print("\nStopping network")
            if self.network:
                self.warcli("network down")
                self.wait_for_all_tanks_status(target="stopped", timeout=60, interval=1)

            print("\nStopping server")
            self.warcli("stop", False)
        except Exception as e:
            # Remove the temporary docker network when we quit.
            # If the warnet server exited prematurely then docker-compose down
            # likely did not succeed or was never executed.
            print(f"Error stopping server: {e}")
            print("Attempting to cleanup docker network")
            try:
                wn = Warnet.from_network(self.network_name)
                wn.warnet_down()
            except Exception as e:
                print(f"Exception thrown cleaning up server, perhaps network never existed?\n{e}")
        finally:
            self.stop_threads.set()
            self.server.terminate()
            self.server.wait()
            self.server_thread.join()
            self.server = None

    # Execute a warcli RPC using command line (always returns string)
    def warcli(self, commands, network=True):
        cmd = ""
        cmd_args = ' '.join(commands.split())
        if self.rust_cli:
            # a temporary hack to fetch the path of the debug binary
            script_path = Path(__file__).resolve()
            project_root = script_path.parent.parent
            warcli_relative_path = Path("target/debug/warcli")
            warcli_absolute_path = project_root / warcli_relative_path
            cmd += f"{warcli_absolute_path} "
            if network:
                cmd += f"--network {self.network_name} "
            cmd += cmd_args
        else:
            cmd += "warcli "
            cmd += cmd_args
            if network:
                cmd += f" --network {self.network_name} "
        cmd = shlex.split(cmd)
        proc = run(cmd, capture_output=True)

        if proc.stderr:
            raise Exception(proc.stderr.decode().strip())
        return proc.stdout.decode().strip()

    # Execute a warnet RPC API call directly (may return dict or list)
    def rpc(self, method, params=None):
        return rpc_call(method, params)

    # Repeatedly execute an RPC until it succeeds
    @exponential_backoff(max_retries=20)
    def wait_for_rpc(self, method, params=None):
        return rpc_call(method, params)

    # Read output from server using a thread
    def output_reader(self, pipe, func):
        while not self.stop_threads.is_set():
            line = pipe.readline().strip()
            if line:
                func(line)

    # Start the Warnet server and wait for RPC interface to respond
    def start_server(self):
        if self.server is not None:
            raise Exception("Server is already running")

        # TODO: check for conflicting warnet process
        #       maybe also ensure that no conflicting docker networks exist

        if self.backend == "k8s":
            # For kubernetes we assume the server is started outside test base
            # but we can still read its log output
            self.server = Popen(
                ["kubectl", "logs", "-f", "rpc-0"],
                stdout=PIPE,
                stderr=STDOUT,
                bufsize=1,
                universal_newlines=True,
            )
        else:
            print(f"\nStarting Warnet server, logging to: {self.logfilepath}")

            self.server = Popen(
                ["warnet", "--backend", self.backend],
                stdout=PIPE,
                stderr=STDOUT,
                bufsize=1,
                universal_newlines=True,
            )

        # Create a thread to read the output
        self.server_thread = threading.Thread(
            target=self.output_reader, args=(self.server.stdout, print)
        )
        self.server_thread.daemon = True
        self.server_thread.start()

        # doesn't require anything container-related
        print("\nWaiting for RPC")
        self.wait_for_rpc("scenarios_available")

    # Quit
    def stop_server(self):
        self.cleanup()

    def wait_for_predicate(self, predicate, timeout=5 * 60, interval=5):
        while True:
            if predicate():
                break
            sleep(interval)
            timeout -= interval
            if timeout < 0:
                raise Exception("Timed out waiting for predicate Truth")

    def get_tank(self, index):
        wn = Warnet.from_network(self.network_name)
        return wn.tanks[index]

    # Poll the warnet server for container status
    # Block until all tanks are running
    def wait_for_all_tanks_status(self, target="running", timeout=20 * 60, interval=5):
        def check_status():
            tanks = self.wait_for_rpc("network_status", {"network": self.network_name})
            stats = {"total": 0}
            for tank in tanks:
                stats["total"] += 1
                bitcoin_status = tank["bitcoin_status"]
                if bitcoin_status not in stats:
                    stats[bitcoin_status] = 0
                stats[bitcoin_status] += 1
                if "lightning_status" in tank:
                    stats["total"] += 1
                    lightning_status = tank["lightning_status"]
                    if lightning_status not in stats:
                        stats[lightning_status] = 0
                    stats[lightning_status] += 1
                if "circuitbreaker_status" in tank:
                    stats["total"] += 1
                    circuitbreaker_status = tank["circuitbreaker_status"]
                    if circuitbreaker_status not in stats:
                        stats[circuitbreaker_status] = 0
                    stats[circuitbreaker_status] += 1
            print(f"Waiting for all tanks to reach '{target}': {stats}")
            # All tanks are running, proceed
            return target in stats and stats[target] == stats["total"]

        self.wait_for_predicate(check_status, timeout, interval)

    # Ensure all tanks have all the connections they are supposed to have
    # Block until all success
    def wait_for_all_edges(self, timeout=20 * 60, interval=5):
        def check_status():
            return self.wait_for_rpc("network_connected", {"network": self.network_name})

        self.wait_for_predicate(check_status, timeout, interval)

    def wait_for_all_scenarios(self):
        def check_scenarios():
            scns = self.rpc("scenarios_list_running")
            return all(not scn["active"] for scn in scns)

        self.wait_for_predicate(check_scenarios)
