import argparse
import base64
import json
import logging
import logging.config
import os
import pkgutil
import platform
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from datetime import datetime
from io import BytesIO
from pathlib import Path

import jsonschema
import networkx as nx
import scenarios
from backends import ServiceType
from flask import Flask, jsonify, request
from flask_jsonrpc.app import JSONRPC
from flask_jsonrpc.exceptions import ServerError
from warnet.utils import (
    create_cycle_graph,
    gen_config_dir,
    validate_graph_schema,
)
from warnet.warnet import Warnet

WARNET_SERVER_PORT = 9276
CONFIG_DIR_ALREADY_EXISTS = 32001
LOGGING_CONFIG_PATH = Path("src/logging_config/config.json")


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
        self.jsonrpc = JSONRPC(self.app, "/api")

        self.log_file_path = os.path.join(self.basedir, "warnet.log")
        self.setup_global_exception_handler()
        self.setup_logging()
        self.setup_rpc()
        self.warnets: dict = dict()
        self.logger.info("Started server")

        # register a well known /-/healthy endpoint for liveness tests
        # we regard warnet as healthy if the http server is up
        # /-/healthy and /-/ready are often used (e.g. by the prometheus server)
        self.app.add_url_rule("/-/healthy", view_func=self.healthy)

        # This is set while we bring a warnet up, which may include building a new image
        # After warnet is up this will be released.
        # This is used to delay api calls which rely on and image being built dynamically
        # before the config dir is populated with the deployment info
        self.image_build_lock = threading.Lock()

    def setup_global_exception_handler(self):
        """
        Use flask to log traceback of unhandled excpetions
        """

        @self.app.errorhandler(Exception)
        def handle_exception(e):
            trace = traceback.format_exc()
            self.logger.error(f"Unhandled exception: {e}\n{trace}")
            response = {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": "Internal server error",
                    "data": str(e),
                },
                "id": request.json.get("id", None) if request.json else None,
            }
            return jsonify(response), 500

    def healthy(self):
        return "warnet is healthy"

    def setup_logging(self):
        os.makedirs(os.path.dirname(self.log_file_path), exist_ok=True)

        with open(LOGGING_CONFIG_PATH) as f:
            logging_config = json.load(f)

        # Update log file path
        logging_config["handlers"]["file"]["filename"] = str(self.log_file_path)

        # Apply the config
        logging.config.dictConfig(logging_config)

        self.logger = logging.getLogger("warnet")
        self.logger.info("Logging started")

        def log_request():
            if "healthy" in request.path:
                return  # No need to log all these
            if not request.path.startswith("/api"):
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
            raise Exception(
                f"Failed to acquire the build lock within {timeout} seconds, aborting RPC."
            )

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
        self.jsonrpc.register(self.scenarios_run_file)
        self.jsonrpc.register(self.scenarios_stop)
        self.jsonrpc.register(self.scenarios_list_running)
        # Networks
        self.jsonrpc.register(self.network_up)
        self.jsonrpc.register(self.network_from_file)
        self.jsonrpc.register(self.network_down)
        self.jsonrpc.register(self.network_info)
        self.jsonrpc.register(self.network_status)
        self.jsonrpc.register(self.network_connected)
        self.jsonrpc.register(self.network_export)
        # Graph
        self.jsonrpc.register(self.graph_generate)
        self.jsonrpc.register(self.graph_validate)
        # Debug
        self.jsonrpc.register(self.generate_deployment)
        self.jsonrpc.register(self.exec_run)
        # Server
        self.jsonrpc.register(self.server_stop)
        # Logs
        self.jsonrpc.register(self.logs_grep)

    def get_warnet(self, network: str) -> Warnet:
        """
        Will get a warnet from the cache if it exists.
        Otherwise it will create the network using from_network() and save it
        to the cache before returning it.
        """
        if network in self.warnets:
            return self.warnets[network]
        wn = Warnet.from_network(network, self.backend)
        if isinstance(wn, Warnet):
            self.warnets[network] = wn
            return wn
        raise ServerError(f"Could not find warnet {network}")

    def tank_bcli(
        self, node: int, method: str, params: list[str] | None = None, network: str = "warnet"
    ) -> str:
        """
        Call bitcoin-cli on <node> <method> <params> in [network]
        """
        wn = self.get_warnet(network)
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
        wn = self.get_warnet(network)
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
        wn = self.get_warnet(network)
        try:
            messages = [
                msg
                for msg in wn.container_interface.get_messages(
                    wn.tanks[node_a].index, wn.tanks[node_b].index, wn.bitcoin_network
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
            wn = self.get_warnet(network)
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

    def scenarios_run_file(
        self, scenario_base64: str, additional_args: list[str], network: str = "warnet"
    ) -> str:
        scenario_path = None
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as temp_file:
            scenario_path = temp_file.name

            # decode base64 string to binary
            scenario_bytes = base64.b64decode(scenario_base64)
            # write binary to file
            temp_file.write(scenario_bytes)

        if not os.path.exists(scenario_path):
            raise ServerError(f"Scenario not found at {scenario_path}.")

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
                    "cmd": f"{scenario_path} {' '.join(additional_args)}",
                    "proc": proc,
                    "network": network,
                }
            )

            return f"Running scenario with PID {proc.pid} in the background..."

        except Exception as e:
            msg = f"Error running scenario: {e}"
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

        def thread_start(server: Server, network):
            try:
                wn = server.get_warnet(network)
                wn.apply_network_conditions()
                wn.wait_for_health()
                server.logger.info(
                    f"Successfully resumed warnet named '{network}' from config dir {wn.config_dir}"
                )
            except Exception as e:
                trace = traceback.format_exc()
                server.logger.error(f"Unhandled exception bringing network up: {e}\n{trace}")

        try:
            t = threading.Thread(target=lambda: thread_start(self, network))
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

        def thread_start(server: Server, network):
            with server.image_build_lock:
                try:
                    wn = server.get_warnet(network)
                    wn.generate_deployment()
                    wn.write_fork_observer_config()
                    wn.warnet_build()
                    wn.warnet_up()
                    wn.wait_for_health()
                    wn.apply_network_conditions()
                    self.logger.info("Warnet started successfully")
                except Exception as e:
                    trace = traceback.format_exc()
                    self.logger.error(f"Unhandled exception starting warnet: {e}\n{trace}")

        config_dir = gen_config_dir(network)
        if config_dir.exists():
            if force:
                shutil.rmtree(config_dir)
            else:
                message = f"Config dir {config_dir} already exists, not overwriting existing warnet without --force"
                self.logger.error(message)
                raise ServerError(message=message, code=CONFIG_DIR_ALREADY_EXISTS)

        try:
            self.warnets[network] = Warnet.from_graph_file(
                graph_file, config_dir, network, self.backend
            )
            t = threading.Thread(target=lambda: thread_start(self, network))
            t.daemon = True
            t.start()
            return self.warnets[network]._warnet_dict_representation()
        except Exception as e:
            msg = f"Error bring up warnet: {e}"
            self.logger.error(msg)
            raise ServerError(message=msg) from e

    def graph_generate(
        self,
        n: int,
        outfile: str,
        version: str,
        bitcoin_conf: str | None = None,
        random: bool = False,
    ) -> str:
        try:
            graph = create_cycle_graph(n, version, bitcoin_conf, random)

            if outfile:
                file_path = Path(outfile)
                nx.write_graphml(graph, file_path, named_key_ids=True)
                return f"Generated graph written to file: {outfile}"
            bio = BytesIO()
            nx.write_graphml(graph, bio, named_key_ids=True)
            xml_data = bio.getvalue()
            return xml_data.decode("utf-8")
        except Exception as e:
            msg = f"Error generating graph: {e}"
            self.logger.error(msg)
            raise ServerError(message=msg) from e

    def graph_validate(self, graph_path: str) -> str:
        with open(graph_path) as f:
            graph = nx.parse_graphml(f.read(), node_type=int, force_multigraph=True)
        try:
            validate_graph_schema(graph)
        except (jsonschema.ValidationError, jsonschema.SchemaError) as e:
            raise ServerError(message=f"Schema of {graph_path} is invalid: {e}") from e
        return f"Schema of {graph_path} is valid"

    def network_down(self, network: str = "warnet") -> str:
        """
        Stop all containers in <network>.
        """
        wn = self.get_warnet(network)
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
        wn = self.get_warnet(network)
        return wn._warnet_dict_representation()

    def network_status(self, network: str = "warnet") -> list[dict]:
        """
        Get running status of a warnet network named <network>
        """
        try:
            wn = self.get_warnet(network)
            stats = []
            for tank in wn.tanks:
                status = {"tank_index": tank.index, "bitcoin_status": tank.status.name.lower()}
                if tank.lnnode is not None:
                    status["lightning_status"] = tank.lnnode.status.name.lower()
                    if tank.lnnode.cb is not None:
                        status["circuitbreaker_status"] = tank.lnnode.cb_status.name.lower()
                stats.append(status)
            return stats
        except Exception as e:
            msg = f"Error getting network status: {e}"
            self.logger.error(msg)
            raise ServerError(message=msg) from e

    def network_connected(self, network: str = "warnet") -> bool:
        """
        Indicate whether all of the graph edges are connected in <network>
        """
        try:
            wn = self.get_warnet(network)
            return wn.network_connected()
        except Exception as e:
            self.logger.error(f"{e}")
            return False

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
            wn = self.get_warnet(network)
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
            wn = self.get_warnet(network)
            return wn.container_interface.logs_grep(pattern, network)
        except Exception as e:
            msg = f"Error grepping logs using pattern {pattern}: {e}"
            self.logger.error(msg)
            raise ServerError(message=msg) from e

    def exec_run(self, index: int, service_type: int, cmd: str, network: str = "warnet") -> str:
        """
        Execute an arbitrary command in an arbitrary container,
        identified by tank index and ServiceType
        """
        wn = self.get_warnet(network)
        return wn.container_interface.exec_run(index, ServiceType(service_type), cmd)


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
