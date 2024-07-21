import argparse
import base64
import importlib
import importlib.resources as pkg_resources
import io
import json
import logging
import logging.config
import os
import pkgutil
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import traceback
from datetime import datetime

import warnet.scenarios as scenarios
from flask import Flask, jsonify, request
from flask_jsonrpc.app import JSONRPC
from flask_jsonrpc.exceptions import ServerError

from .services import ServiceType
from .utils import gen_config_dir
from .warnet import Warnet

WARNET_SERVER_PORT = 9276
CONFIG_DIR_ALREADY_EXISTS = 32001


class Server:
    def __init__(self):
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
        with pkg_resources.open_text("warnet.logging_config", "config.json") as f:
            logging_config = json.load(f)
        logging_config["handlers"]["file"]["filename"] = str(self.log_file_path)
        logging.config.dictConfig(logging_config)
        self.logger = logging.getLogger("server")
        self.scenario_logger = logging.getLogger("scenario")
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
        self.jsonrpc.register(self.tank_ln_pub_key)
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
        # Debug
        self.jsonrpc.register(self.generate_deployment)
        self.jsonrpc.register(self.exec_run)
        # Logs
        self.jsonrpc.register(self.logs_grep)

    def scenario_log(self, proc):
        while not proc.stdout:
            time.sleep(0.1)
        for line in proc.stdout:
            self.scenario_logger.info(line.decode().rstrip())

    def get_warnet(self, network: str) -> Warnet:
        """
        Will get a warnet from the cache if it exists.
        Otherwise it will create the network using from_network() and save it
        to the cache before returning it.
        """
        if network in self.warnets:
            return self.warnets[network]
        wn = Warnet.from_network(network)
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

    def tank_ln_pub_key(self, node: int, network: str = "warnet") -> str:
        """
        Get lightning pub key on <node> in [network]
        """
        wn = self.get_warnet(network)
        try:
            return wn.container_interface.ln_pub_key(wn.tanks[node])
        except Exception as e:
            msg = f"Error getting pub key: {e}"
            self.logger.error(msg)
            raise ServerError(message=msg) from e

    def tank_debug_log(self, network: str, node: int) -> str:
        """
        Fetch the Bitcoin Core debug log from <node>
        """
        wn = Warnet.from_network(network)
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

    def network_export(self, network: str, activity: str | None, exclude: list[int]) -> bool:
        """
        Export all data for a simln container running on the network
        """
        wn = self.get_warnet(network)
        if "simln" not in wn.services:
            raise Exception("No simln service in network")

        # JSON object that will eventually be written to simln config file
        config = {"nodes": []}
        if activity:
            config["activity"] = json.loads(activity)
        # In-memory file to build tar archive
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w") as tar_file:
            # tank LN nodes add their credentials to tar archive
            wn.export(config, tar_file, exclude=exclude)
            # write config file
            config_bytes = json.dumps(config).encode("utf-8")
            config_stream = io.BytesIO(config_bytes)
            tarinfo = tarfile.TarInfo(name="sim.json")
            tarinfo.size = len(config_bytes)
            tar_file.addfile(tarinfo=tarinfo, fileobj=config_stream)

        # Write the archive to the RPC server's config directory
        source_file = wn.config_dir / "simln.tar"
        with open(source_file, "wb") as output:
            tar_buffer.seek(0)
            output.write(tar_buffer.read())

        # Copy the archive to the "emptydir" volume in the simln pod
        wn.container_interface.write_service_config(source_file, "simln", "/simln/")
        return True

    def scenarios_available(self) -> list[tuple]:
        """
        List available scenarios in the Warnet Test Framework
        """
        try:
            scenario_list = []
            for s in pkgutil.iter_modules(scenarios.__path__):
                module_name = f"warnet.scenarios.{s.name}"
                try:
                    m = importlib.import_module(module_name)
                    if hasattr(m, "cli_help"):
                        scenario_list.append((s.name, m.cli_help()))
                except ModuleNotFoundError as e:
                    print(f"Module not found: {module_name}, error: {e}")
                    raise
            return scenario_list
        except Exception as e:
            msg = f"Error listing scenarios: {e}"
            self.logger.error(msg)
            raise ServerError(message=msg) from e

    def _start_scenario(
        self,
        scenario_path: str,
        scenario_name: str,
        additional_args: list[str],
        network: str,
    ) -> str:
        try:
            run_cmd = [sys.executable, scenario_path] + additional_args + [f"--network={network}"]
            self.logger.debug(f"Running {run_cmd}")
            proc = subprocess.Popen(
                run_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            t = threading.Thread(target=lambda: self.scenario_log(proc))
            t.daemon = True
            t.start()
            self.running_scenarios.append(
                {
                    "pid": proc.pid,
                    "cmd": f"{scenario_name} {' '.join(additional_args)}",
                    "proc": proc,
                    "network": network,
                }
            )
            return f"Running scenario {scenario_name} with PID {proc.pid} in the background..."
        except Exception as e:
            msg = f"Error running scenario: {e}"
            self.logger.error(msg)
            raise ServerError(message=msg) from e

    def scenarios_run_file(
        self,
        scenario_base64: str,
        scenario_name: str,
        additional_args: list[str],
        network: str = "warnet",
    ) -> str:
        # Extract just the filename without path and extension
        with tempfile.NamedTemporaryFile(
            prefix=scenario_name,
            suffix=".py",
            delete=False,
        ) as temp_file:
            scenario_path = temp_file.name
            temp_file.write(base64.b64decode(scenario_base64))

        if not os.path.exists(scenario_path):
            raise ServerError(f"Scenario not found at {scenario_path}.")

        return self._start_scenario(scenario_path, scenario_name, additional_args, network)

    def scenarios_run(
        self, scenario: str, additional_args: list[str], network: str = "warnet"
    ) -> str:
        # Use importlib.resources to get the scenario path
        scenario_package = "warnet.scenarios"
        scenario_filename = f"{scenario}.py"

        # Ensure the scenario file exists within the package
        with importlib.resources.path(scenario_package, scenario_filename) as scenario_path:
            scenario_path = str(scenario_path)  # Convert Path object to string

        if not os.path.exists(scenario_path):
            raise ServerError(f"Scenario {scenario} not found at {scenario_path}.")

        return self._start_scenario(scenario_path, scenario, additional_args, network)

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
                "return_code": sc["proc"].returncode,
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
                graph_file,
                config_dir,
                network,
            )
            t = threading.Thread(target=lambda: thread_start(self, network))
            t.daemon = True
            t.start()
            return self.warnets[network]._warnet_dict_representation()
        except Exception as e:
            msg = f"Error bring up warnet: {e}"
            self.logger.error(msg)
            raise ServerError(message=msg) from e

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
        "--dev", action="store_true", help="Run in development mode with debug enabled"
    )
    args = parser.parse_args()
    debug_mode = args.dev
    server = Server()
    server.app.run(host="0.0.0.0", port=WARNET_SERVER_PORT, debug=debug_mode)


if __name__ == "__main__":
    run_server()
