import argparse
import logging
import os
import pkgutil
import platform
import shutil
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime
from io import BytesIO
from logging import StreamHandler
from logging.handlers import RotatingFileHandler
from pathlib import Path

import networkx as nx
import scenarios
from flask import Flask, request
from flask_jsonrpc.app import JSONRPC
from flask_jsonrpc.exceptions import ServerError
from warnet.utils import (
    create_graph_with_probability,
    gen_config_dir,
)
from warnet.warnet import Warnet

# Breaking API changes should bump/change this for k8s
SERVER_VERSION = "0.1"
WARNET_SERVER_PORT = 9276
CONFIG_DIR_ALREADY_EXISTS = 32001


class Server:
    def __init__(self, backend):
        self.backend = backend
        system = os.name
        if system == "nt" or platform.system() == "Windows":
            self.basedir = os.path.join(os.path.expanduser("~"), "warnet")
        elif system == "posix" or platform.system() == "Linux" or platform.system() == "Darwin":
            self.basedir = os.environ.get("XDG_STATE_HOME")
            if self.basedir is None:
                # ~/.warnet/warnet.log
                self.basedir = os.path.join(os.environ["HOME"], ".warnet")
            else:
                # XDG_STATE_HOME / warnet / warnet.log
                self.basedir = os.path.join(self.basedir, "warnet")
        else:
            raise NotImplementedError("Unsupported operating system")

        self.running_scenarios = []

        self.app = Flask(__name__)
        self.jsonrpc = JSONRPC(self.app, f"/api/{SERVER_VERSION}")

        self.log_file_path = os.path.join(self.basedir, "warnet.log")
        self.logger: logging.Logger
        self.setup_logging()
        self.setup_rpc()
        self.logger.info(f"Started server version {SERVER_VERSION}")
        self.app.add_url_rule("/-/healthy", view_func=self.healthy)

        # register a well known /-/healthy endpoint for liveness tests
        # we regard warnet as healthy if the http server is up
        # /-/healthy and /-/ready are often used (e.g. by the prometheus server)
        self.app.add_url_rule("/-/healthy", view_func=self.healthy)

        # This is set while we bring a warnet up, which may include building a new image
        # After warnet is up this will be released.
        # This is used to delay api calls which rely on and image being built dynamically
        # before the config dir is populated with the deployment info
        self.image_build_lock = threading.Lock()

    def healthy(self):
        return "warnet is healthy"

    def setup_logging(self):
        # Ensure the directory exists
        os.makedirs(os.path.dirname(self.log_file_path), exist_ok=True)

        # Configure root logger
        logging.basicConfig(
            level=logging.DEBUG,
            handlers=[
                RotatingFileHandler(
                    self.log_file_path, maxBytes=16_000_000, backupCount=3, delay=True
                ),
                StreamHandler(sys.stdout),
            ],
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        # Disable urllib3.connectionpool logging
        logging.getLogger("urllib3.connectionpool").setLevel(logging.CRITICAL)
        self.logger = logging.getLogger("warnet")
        self.logger.info("Logging started")

        if self.backend == "k8s":
            # if using k8s as a backend, tone the logging down
            logging.getLogger("kubernetes.client.rest").setLevel(logging.WARNING)

        def log_request():
            if not request.path.startswith("/api/"):
                self.logger.debug(request.path)
            else:
                self.logger.debug(request.json)

        def build_check():
            timeout = 600
            check_interval = 10
            time_elapsed = 0

            while time_elapsed < timeout:
                # Attempt to acquire the lock without blocking
                lock_acquired = self.image_build_lock.acquire(blocking=False)
                # If we get the lock, release it and continue
                if lock_acquired:
                    self.image_build_lock.release()
                    return
                # Otherwise wait before trying again
                else:
                    time.sleep(check_interval)
                    time_elapsed += check_interval

            # If we've reached here, the lock wasn't acquired in time
            raise Exception(f"Failed to acquire the build lock within {timeout} seconds, aborting RPC.")

        self.app.before_request(log_request)
        self.app.before_request(build_check)

    def setup_rpc(self):
        # Tanks
        self.jsonrpc.register(self.tank_bcli)
        self.jsonrpc.register(self.tank_lncli)
        self.jsonrpc.register(self.tank_debug_log)
        self.jsonrpc.register(self.tank_messages)
        # Scenarios
        self.jsonrpc.register(self.scenarios_available)
        self.jsonrpc.register(self.scenarios_run)
        self.jsonrpc.register(self.scenarios_stop)
        self.jsonrpc.register(self.scenarios_list_running)
        # Networks
        self.jsonrpc.register(self.network_up)
        self.jsonrpc.register(self.network_from_file)
        self.jsonrpc.register(self.network_down)
        self.jsonrpc.register(self.network_info)
        self.jsonrpc.register(self.network_status)
        self.jsonrpc.register(self.network_export)
        # Graph
        self.jsonrpc.register(self.graph_generate)
        # Debug
        self.jsonrpc.register(self.generate_deployment)
        # Server
        self.jsonrpc.register(self.server_stop)
        # Logs
        self.jsonrpc.register(self.logs_grep)

    def tank_bcli(
        self, node: int, method: str, params: list[str] | None = None, network: str = "warnet"
    ) -> str:
        """
        Call bitcoin-cli on <node> <method> <params> in [network]
        """
        wn = Warnet.from_network(network, self.backend)
        try:
            return wn.container_interface.get_bitcoin_cli(wn.tanks[node], method, params)
        except Exception as e:
            msg = f"Sever error calling bitcoin-cli {method}: {e}"
            self.logger.error(msg)
            raise ServerError(message=msg) from e

    def tank_lncli(self, node: int, command: list[str], network: str = "warnet") -> str:
        """
        Call lightning cli on <node> <command> in [network]
        """
        wn = Warnet.from_network(network, self.backend)
        try:
            return wn.container_interface.ln_cli(wn.tanks[node], command)
        except Exception as e:
            msg = f"Error calling lncli: {e}"
            self.logger.error(msg)
            raise ServerError(message=msg) from e

    def tank_debug_log(self, network: str, node: int) -> str:
        """
        Fetch the Bitcoin Core debug log from <node>
        """
        wn = Warnet.from_network(network, self.backend)
        try:
            return wn.container_interface.get_bitcoin_debug_log(wn.tanks[node].index)
        except Exception as e:
            msg = f"Error fetching debug logs: {e}"
            self.logger.error(msg)
            raise ServerError(message=msg) from e

    def tank_messages(self, network: str, node_a: int, node_b: int) -> str:
        """
        Fetch messages sent between <node_a> and <node_b>.
        """
        wn = Warnet.from_network(network, self.backend)
        try:
            messages = [
                msg
                for msg in wn.container_interface.get_messages(
                    wn.tanks[node_a].index, wn.tanks[node_b].ipv4, wn.bitcoin_network
                )
                if msg is not None
            ]
            if not messages:
                msg = f"No messages found between {node_a} and {node_b}"
                self.logger.error(msg)
                raise ServerError(message=msg)

            messages_str_list = []

            for message in messages:
                # Check if 'time' key exists and its value is a number
                if not (message.get("time") and isinstance(message["time"], int | float)):
                    continue

                timestamp = datetime.utcfromtimestamp(message["time"] / 1e6).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                direction = ">>>" if message.get("outbound", False) else "<<<"
                msgtype = message.get("msgtype", "")
                body_dict = message.get("body", {})

                if not isinstance(body_dict, dict):  # messages will be in dict form
                    continue

                body_str = ", ".join(f"{key}: {value}" for key, value in body_dict.items())
                messages_str_list.append(f"{timestamp} {direction} {msgtype} {body_str}")

            result_str = "\n".join(messages_str_list)

            return result_str

        except Exception as e:
            msg = f"Error fetching messages between nodes {node_a} and {node_b}: {e}"
            self.logger.error(msg)
            raise ServerError(message=msg) from e

    def network_export(self, network: str) -> str:
        """
        Export all data for sim-ln to subdirectory
        """
        try:
            wn = Warnet.from_network(network)
            subdir = os.path.join(wn.config_dir, "simln")
            os.makedirs(subdir, exist_ok=True)
            wn.export(subdir)
            return subdir
        except Exception as e:
            msg = f"Error exporting network: {e}"
            self.logger.error(msg)
            raise ServerError(message=msg) from e

    def scenarios_available(self) -> list[tuple]:
        """
        List available scenarios in the Warnet Test Framework
        """
        try:
            scenario_list = []
            for s in pkgutil.iter_modules(scenarios.__path__):
                m = pkgutil.resolve_name(f"scenarios.{s.name}")
                if hasattr(m, "cli_help"):
                    scenario_list.append((s.name, m.cli_help()))
            return scenario_list
        except Exception as e:
            msg = f"Error listing scenarios: {e}"
            self.logger.error(msg)
            raise ServerError(message=msg) from e

    def scenarios_run(
        self, scenario: str, additional_args: list[str], network: str = "warnet"
    ) -> str:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        scenario_path = os.path.join(base_dir, "scenarios", f"{scenario}.py")

        if not os.path.exists(scenario_path):
            raise ServerError(f"Scenario {scenario} not found at {scenario_path}.")

        try:
            run_cmd = (
                [sys.executable, scenario_path]
                + additional_args
                + [f"--network={network}", f"--backend={self.backend}"]
            )
            self.logger.debug(f"Running {run_cmd}")

            proc = subprocess.Popen(
                run_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            def proc_logger():
                while not proc.stdout:
                    time.sleep(0.1)
                for line in proc.stdout:
                    self.logger.info(line.decode().rstrip())

            t = threading.Thread(target=lambda: proc_logger())
            t.daemon = True
            t.start()

            self.running_scenarios.append(
                {
                    "pid": proc.pid,
                    "cmd": f"{scenario} {' '.join(additional_args)}",
                    "proc": proc,
                    "network": network,
                }
            )

            return f"Running scenario {scenario} with PID {proc.pid} in the background..."

        except Exception as e:
            msg = f"Error running scenario: {e}"
            self.logger.error(msg)
            raise ServerError(message=msg) from e

    def scenarios_stop(self, pid: int) -> str:
        matching_scenarios = [sc for sc in self.running_scenarios if sc["pid"] == pid]
        if matching_scenarios:
            matching_scenarios[0]["proc"].terminate()  # sends SIGTERM
            # Remove from running list
            self.running_scenarios = [sc for sc in self.running_scenarios if sc["pid"] != pid]
            return f"Stopped scenario with PID {pid}."
        else:
            msg = f"Could not find scenario with PID {pid}"
            self.logger.error(msg)
            raise ServerError(message=msg)

    def scenarios_list_running(self) -> list[dict]:
        running = [
            {
                "pid": sc["pid"],
                "cmd": sc["cmd"],
                "active": sc["proc"].poll() is None,
                "network": sc["network"],
            }
            for sc in self.running_scenarios
        ]
        return running

    def network_up(self, network: str = "warnet") -> str:
        def thread_start(wn):
            try:
                # wn.container_interface.up()
                # Update warnet from docker here to get ip addresses
                wn = Warnet.from_network(network, self.backend)
                wn.apply_network_conditions()
                wn.connect_edges()
                self.logger.info(
                    f"Resumed warnet named '{network}' from config dir {wn.config_dir}"
                )
            except Exception as e:
                msg = f"Error starting network: {e}"
                self.logger.error(msg)

        try:
            wn = Warnet.from_network(network, self.backend)
            t = threading.Thread(target=lambda: thread_start(wn))
            t.daemon = True
            t.start()
            return "Resuming warnet..."
        except Exception as e:
            msg = f"Error bring up warnet: {e}"
            self.logger.error(msg)
            raise ServerError(message=msg) from e

    def network_from_file(
        self, graph_file: str, force: bool = False, network: str = "warnet"
    ) -> dict:
        """
        Run a warnet with topology loaded from a <graph_file>
        """

        def thread_start(wn, lock: threading.Lock):
            with lock:
                try:
                    wn.generate_deployment()
                    # wn.write_fork_observer_config()
                    wn.warnet_build()
                    wn.warnet_up()
                    wn.apply_network_conditions()
                    wn.connect_edges()
                except Exception as e:
                    msg = f"Error starting warnet: {e}"
                    self.logger.error(msg)

        config_dir = gen_config_dir(network)
        if config_dir.exists():
            if force:
                shutil.rmtree(config_dir)
            else:
                message = f"Config dir {config_dir} already exists, not overwriting existing warnet without --force"
                self.logger.error(message)
                raise ServerError(message=message, code=CONFIG_DIR_ALREADY_EXISTS)

        try:
            wn = Warnet.from_graph_file(graph_file, config_dir, network, self.backend)
            t = threading.Thread(target=lambda: thread_start(wn, self.image_build_lock))
            t.daemon = True
            t.start()
            return wn._warnet_dict_representation()
        except Exception as e:
            msg = f"Error bring up warnet: {e}"
            self.logger.error(msg)
            raise ServerError(message=msg) from e

    def graph_generate(
        self,
        params: list[str],
        outfile: str,
        version: str,
        bitcoin_conf: str | None = None,
        random: bool = False,
    ) -> str:
        try:
            graph_func = nx.generators.erdos_renyi_graph
            # Default connectivity probability of 0.2
            if not any(param.startswith("p=") for param in params):
                params.append("p=0.2")

            graph = create_graph_with_probability(graph_func, params, version, bitcoin_conf, random)

            if outfile:
                file_path = Path(outfile)
                nx.write_graphml(graph, file_path)
                return f"Generated graph written to file: {outfile}"
            bio = BytesIO()
            nx.write_graphml(graph, bio)
            xml_data = bio.getvalue()
            return xml_data.decode('utf-8')
        except Exception as e:
            msg = f"Error generating graph: {e}"
            self.logger.error(msg)
            raise ServerError(message=msg) from e

    def network_down(self, network: str = "warnet") -> str:
        """
        Stop all containers in <network>.
        """
        wn = Warnet.from_network(network, self.backend)
        try:
            wn.warnet_down()
            return "Stopping warnet"
        except Exception as e:
            msg = f"Error bringing warnet down: {e}"
            self.logger.error(msg)
            raise ServerError(message=msg) from e

    def network_info(self, network: str = "warnet") -> dict:
        """
        Get info about a warnet network named <network>
        """
        wn = Warnet.from_network(network, self.backend)
        return wn._warnet_dict_representation()

    def network_status(self, network: str = "warnet") -> list[dict]:
        """
        Get running status of a warnet network named <network>
        """
        try:
            wn = Warnet.from_network(network, self.backend)
            stats = []
            for tank in wn.tanks:
                status = {"tank_index": tank.index, "bitcoin_status": tank.status.name.lower()}
                if tank.lnnode is not None:
                    status["lightning_status"] = tank.lnnode.status.name.lower()
                stats.append(status)
            return stats
        except Exception as e:
            msg = f"Error getting network status: {e}"
            self.logger.error(msg)
            raise ServerError(message=msg) from e

    def generate_deployment(self, graph_file: str, network: str = "warnet") -> str:
        """
        Generate the deployment file for a graph file
        """
        try:
            config_dir = gen_config_dir(network)
            if config_dir.exists():
                message = f"Config dir {config_dir} already exists, not overwriting existing warnet without --force"
                self.logger.error(message)
                raise ServerError(message=message, code=CONFIG_DIR_ALREADY_EXISTS)
            wn = Warnet.from_graph_file(graph_file, config_dir, network, self.backend)
            wn.generate_deployment()
            if not wn.deployment_file or not wn.deployment_file.is_file():
                raise ServerError(f"No deployment file found at {wn.deployment_file}")
            with open(wn.deployment_file) as f:
                return f.read()
        except Exception as e:
            msg = f"Error generating deployment file: {e}"
            self.logger.error(msg)
            raise ServerError(message=msg) from e

    def server_stop(self) -> None:
        """
        Stop warnet.
        """
        pid = os.getpid()
        self.logger.info("Gracefully shutting down server...")
        # in debug mode Flask likes to recieve ctrl+c to shutdown gracefully
        os.kill(pid, signal.SIGINT)

    def logs_grep(self, pattern: str, network: str = "warnet") -> str:
        """
        Grep the logs from the fluentd container for a regex pattern
        """
        try:
            wn = Warnet.from_network(network, self.backend)
            return wn.container_interface.logs_grep(pattern, network)
        except Exception as e:
            msg = f"Error grepping logs using pattern {pattern}: {e}"
            self.logger.error(msg)
            raise ServerError(message=msg) from e


def run_server():
    parser = argparse.ArgumentParser(description="Run the server")
    parser.add_argument(
        "--backend",
        type=str,
        default="compose",
        choices=["compose", "k8s"],
        help="Specify the backend to use",
    )
    parser.add_argument(
        "--dev", action="store_true", help="Run in development mode with debug enabled"
    )

    args = parser.parse_args()

    if args.backend not in ["compose", "k8s"]:
        print(f"Invalid backend {args.backend}")
        sys.exit(1)

    debug_mode = args.dev
    server = Server(args.backend)

    server.app.run(host="0.0.0.0", port=WARNET_SERVER_PORT, debug=debug_mode)


if __name__ == "__main__":
    run_server()
