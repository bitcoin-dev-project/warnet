import atexit
import threading
from pathlib import Path
from subprocess import Popen, run, PIPE
from tempfile import mkdtemp
from time import sleep
from typing import Optional
from warnet.cli.rpc import rpc_call
from warnet.warnet import Warnet
from warnet.utils import exponential_backoff

class TestBase:
    def __init__(self):
        # Warnet server stdout gets logged here
        self.tmpdir = Path(mkdtemp(prefix="warnet_test_"))
        self.logfilepath = self.tmpdir / "warnet.log"

        # Use the same dir name for the warnet network name
        self.network_name = self.tmpdir.name
        self.logfile = None
        self.server: Optional[Popen] = None
        self.cleaned_up = False

        atexit.register(self.cleanup)

        print(f"\nWarnet test base started")

    def cleanup_server(self):
        self.warcli("stop")
        sleep(2)
        if self.server.poll() is None:
            # kill it!
            print("Error stopping server using `warcli stop`, killing with terminate()")
            self.server.terminate()
            self.server.wait()

    def cleanup_network(self):
        try:
            print("\nStopping network")
            self.warcli("network down")

            self.wait_for_all_tanks_status(target="none", timeout=60, interval=1)

        except Exception as e:
            # Remove the temporary docker network when we quit.
            # If the warnet server exited prematurely then docker-compose down
            # likely did not succeed or was never executed.
            print(f"Error stopping server: {e}")
            print("Attempting to force cleanup of docker network")
            wn = Warnet.from_network(self.network_name)
            wn.warnet_down()

    def cleanup(self, signum = None, frame = None):
        if self.cleaned_up:
            return

        self.cleanup_network()
        self.cleanup_server()
        self.cleaned_up = True

    # Execute a warcli RPC using command line (always returns string)
    def warcli(self, str, network=True):
        cmd = ["warcli"] + str.split()
        if network:
            cmd += ["--network", self.network_name]
        proc = run(
            cmd,
            stdout=PIPE,
            stderr=PIPE)
        return proc.stdout.decode().strip()

    # Execute a warnet RPC API call directly (may return dict or list)
    def rpc(self, method, params = []):
        return rpc_call(method, params)

    # Repeatedly execute an RPC until it succeeds
    @exponential_backoff()
    def wait_for_rpc(self, method, params = []):
        return rpc_call(method, params)

    def output_reader(self, pipe):
        """
        Write stdout and stderr to stdout and a file
        """
        with open(self.logfilepath, 'a') as logfile:
            for line in iter(pipe.readline, b''):
                line_decoded = line.decode('utf-8')
                print(line_decoded, end='')  # Print to main STDOUT
                logfile.write(line_decoded)
                logfile.flush()

    # Start the Warnet server and wait for RPC interface to respond
    def start_server(self):
        if self.server is not None:
            raise Exception("Server is already running")

        # TODO: check for conflicting warnet process
        #       maybe also ensure that no conflicting docker networks exist

        print(f"\nStarting Warnet server, logging to: {self.logfilepath}")
        self.server = Popen(["warnet"], stdout=PIPE, stderr=PIPE)

        # capture STDOUT and STDERR using threads
        stdout_thread = threading.Thread(target=self.output_reader, args=(self.server.stdout,), daemon=True)
        stderr_thread = threading.Thread(target=self.output_reader, args=(self.server.stderr,), daemon=True)
        stdout_thread.start()
        stderr_thread.start()

        print("\nWaiting for RPC")
        # doesn't require anything docker-related
        self.wait_for_rpc("scenarios_list")

    # Quit
    def stop_server(self):
        self.cleanup()
        sleep(1) # Give reader std* threads a second to process final output

    def wait_for_predicate(self, predicate, timeout=5*60, interval=5):
        while True:
            if predicate():
                break
            sleep(interval)
            timeout -= interval
            if timeout < 0:
                raise Exception(f"Timed out waiting for predicate Truth")

    def get_tank(self, index):
        wn = Warnet.from_network(self.network_name)
        return wn.tanks[index]

    # Poll the warnet server for container status
    # Block until all tanks are running
    def wait_for_all_tanks_status(self, target="running", timeout=20*60, interval=5):
        def check_status():
            tanks = self.rpc("network_status", {"network": self.network_name})
            stats = {
                "total": len(tanks)
            }
            for tank in tanks:
                status = tank["status"] if tank["status"] is not None else "none"
                if status not in stats:
                    stats[status] = 0
                stats[status] += 1
            print(f"Waiting for all tanks to reach '{target}': {stats}")
            # All tanks are running, proceed
            if target in stats and stats[target] == stats["total"]:
                return True
            else:
                return False
        self.wait_for_predicate(check_status, timeout, interval)

