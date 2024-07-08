import atexit
import json
import logging
import logging.config
import os
import threading
from pathlib import Path
from subprocess import PIPE, STDOUT, Popen, run
from tempfile import mkdtemp
from time import sleep

from cli.rpc import rpc_call
from warnet.server import LOGGING_CONFIG_PATH
from warnet.utils import exponential_backoff
from warnet.warnet import Warnet


class TestBase:
    def __init__(self):
        self.setup_environment()
        self.setup_logging()
        atexit.register(self.cleanup)
        self.log.info("Warnet test base initialized")

    def setup_environment(self):
        self.tmpdir = Path(mkdtemp(prefix="warnet-test-"))
        os.environ["XDG_STATE_HOME"] = str(self.tmpdir)
        self.logfilepath = self.tmpdir / "warnet.log"
        # Use the same dir name for the warnet network name
        # replacing underscores which throws off k8s
        self.network_name = self.tmpdir.name.replace("_", "")
        self.server = None
        self.server_thread = None
        self.stop_threads = threading.Event()
        self.network = True

    def setup_logging(self):
        with open(LOGGING_CONFIG_PATH) as f:
            logging_config = json.load(f)
        # Update log file path
        logging_config["handlers"]["file"]["filename"] = str(self.logfilepath)
        # Apply the config
        logging.config.dictConfig(logging_config)
        self.log = logging.getLogger("TestFramework")
        self.log.info("Logging started")

    def cleanup(self, signum=None, frame=None):
        if self.server is None:
            return
        try:
            self.log.info("Stopping network")
            if self.network:
                self.warcli("network down")
                self.wait_for_all_tanks_status(target="stopped", timeout=60, interval=1)
        except Exception as e:
            self.log.error(f"Error bringing network down: {e}")
        finally:
            self.stop_threads.set()
            self.server.terminate()
            self.server.wait()
            self.server_thread.join()
            self.server = None

    def warcli(self, cmd, network=True):
        self.log.debug(f"Executing warcli command: {cmd}")
        command = ["warcli"] + cmd.split()
        if network:
            command += ["--network", self.network_name]
        proc = run(command, capture_output=True)
        if proc.stderr:
            raise Exception(proc.stderr.decode().strip())
        return proc.stdout.decode().strip()

    def rpc(self, method, params=None) -> dict | list:
        """Execute a warnet RPC API call directly"""
        self.log.debug(f"Executing RPC method: {method}")
        return rpc_call(method, params)

    @exponential_backoff(max_retries=20)
    def wait_for_rpc(self, method, params=None):
        """Repeatedly execute an RPC until it succeeds"""
        return self.rpc(method, params)

    def output_reader(self, pipe, func):
        while not self.stop_threads.is_set():
            line = pipe.readline().strip()
            if line:
                func(line)

    def start_server(self):
        """Start the Warnet server and wait for RPC interface to respond"""

        if self.server is not None:
            raise Exception("Server is already running")

        # TODO: check for conflicting warnet process
        #       maybe also ensure that no conflicting docker networks exist

        # For kubernetes we assume the server is started outside test base
        # but we can still read its log output
        self.log.info("Starting Warnet server")
        self.server = Popen(
            ["kubectl", "logs", "-f", "rpc-0"],
            stdout=PIPE,
            stderr=STDOUT,
            bufsize=1,
            universal_newlines=True,
        )

        self.server_thread = threading.Thread(
            target=self.output_reader, args=(self.server.stdout, self.log.debug)
        )
        self.server_thread.daemon = True
        self.server_thread.start()

        self.log.info("Waiting for RPC")
        self.wait_for_rpc("scenarios_available")

    def stop_server(self):
        self.cleanup()

    def wait_for_predicate(self, predicate, timeout=5 * 60, interval=5):
        self.log.debug(f"Waiting for predicate with timeout {timeout}s and interval {interval}s")
        while timeout > 0:
            if predicate():
                return
            sleep(interval)
            timeout -= interval
        import inspect

        raise Exception(
            f"Timed out waiting for Truth from predicate: {inspect.getsource(predicate).strip()}"
        )

    def get_tank(self, index):
        wn = Warnet.from_network(self.network_name)
        return wn.tanks[index]

    def wait_for_all_tanks_status(self, target="running", timeout=20 * 60, interval=5):
        """Poll the warnet server for container status
        Block until all tanks are running
        """

        def check_status():
            tanks = self.wait_for_rpc("network_status", {"network": self.network_name})
            stats = {"total": 0}
            for tank in tanks:
                for service in ["bitcoin", "lightning", "circuitbreaker"]:
                    status = tank.get(f"{service}_status")
                    if status:
                        stats["total"] += 1
                        stats[status] = stats.get(status, 0) + 1
            self.log.info(f"Waiting for all tanks to reach '{target}': {stats}")
            return target in stats and stats[target] == stats["total"]

        self.wait_for_predicate(check_status, timeout, interval)

    def wait_for_all_edges(self, timeout=20 * 60, interval=5):
        """Ensure all tanks have all the connections they are supposed to have
        Block until all success
        """

        def check_status():
            return self.wait_for_rpc("network_connected", {"network": self.network_name})

        self.wait_for_predicate(check_status, timeout, interval)

    def wait_for_all_scenarios(self):
        def check_scenarios():
            scns = self.rpc("scenarios_list_running")
            return all(not scn["active"] for scn in scns)

        self.wait_for_predicate(check_scenarios)
