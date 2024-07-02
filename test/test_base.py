import atexit
import os
import re
import threading
from pathlib import Path
from subprocess import PIPE, STDOUT, Popen, run
from tempfile import mkdtemp
from time import sleep

from cli.rpc import rpc_call
from warnet.utils import exponential_backoff
from warnet.warnet import Warnet


class TestBase:
    def __init__(self):
        # Warnet server stdout gets logged here
        self.tmpdir = Path(mkdtemp(prefix="warnet-test-"))
        os.environ["XDG_STATE_HOME"] = f"{self.tmpdir}"
        self.testlog = self.tmpdir / "testbase.log"

        # Use the same dir name for the warnet network name
        # replacing underscores which throws off k8s
        self.network_name = self.tmpdir.name.replace("_", "")

        self.server = None
        self.server_thread = None
        self.stop_threads = threading.Event()
        self.network = True

        atexit.register(self.cleanup)

        print("\nWarnet test base started")

    def cleanup(self, signum=None, frame=None):
        if self.server is None:
            return

        try:
            print("\nStopping network")
            if self.network:
                self.warcli("network down")
                self.wait_for_all_tanks_status(target="stopped", timeout=60, interval=1)
        except Exception as e:
            print(f"Error bringing network down: {e}")
        finally:
            self.stop_threads.set()
            self.server.terminate()
            self.server.wait()
            self.server_thread.join()
            self.server = None

    # Execute a warcli RPC using command line (always returns string)
    def warcli(self, str, network=True):
        cmd = ["warcli"] + str.split()
        if network:
            cmd += ["--network", self.network_name]
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

        def write_and_print(line):
            if self.testlog.exists():
                with open(self.testlog, 'a') as file:
                    print(line)
                    file.write(f"{line}\n")
            else:
                with open(self.testlog, 'w') as file:
                    print("Creating: ", self.testlog)
                    print(line)
                    file.write(f"{line}\n")

        # For kubernetes we assume the server is started outside test base
        # but we can still read its log output
        self.server = Popen(
            ["kubectl", "logs", "-f", "rpc-0", "--since=1s"],
            stdout=PIPE,
            stderr=STDOUT,
            bufsize=1,
            universal_newlines=True,
        )

        # Create a thread to read the output
        self.server_thread = threading.Thread(
            target=self.output_reader, args=(self.server.stdout, write_and_print)
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


def assert_equal(thing1, thing2, *args):
    if thing1 != thing2 or any(thing1 != arg for arg in args):
        raise AssertionError("not({})".format(" == ".join(str(arg)
                                                          for arg in (thing1, thing2) + args)))


def debug_log_size(debug_log_path, **kwargs) -> int:
    with open(debug_log_path, **kwargs) as dl:
        dl.seek(0, 2)
        return dl.tell()


def assert_log(debug_log_path, expected_msgs, unexpected_msgs=None) -> bool:
    if unexpected_msgs is None:
        unexpected_msgs = []
    assert_equal(type(expected_msgs), list)
    assert_equal(type(unexpected_msgs), list)

    found = True
    with open(debug_log_path, encoding="utf-8", errors="replace") as dl:
        log = dl.read()
    for unexpected_msg in unexpected_msgs:
        if re.search(re.escape(unexpected_msg), log, flags=re.MULTILINE):
            raise AssertionError(
                f'Unexpected message found in log: {unexpected_msg}')
    for expected_msg in expected_msgs:
        if re.search(re.escape(expected_msg), log, flags=re.MULTILINE) is None:
            found = False
    return found
