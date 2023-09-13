import logging
import os
import pkgutil
import shutil
import signal
import subprocess
import sys
import time
import threading
from collections import defaultdict
from datetime import datetime
from logging.handlers import RotatingFileHandler
from logging import StreamHandler
from typing import List, Dict
from flask import Flask, request
from flask_jsonrpc.app import JSONRPC

import scenarios
from warnet.warnet import Warnet
from warnet.client import (
    get_bitcoin_cli,
    get_bitcoin_debug_log,
    get_messages,
    compose_down,
)
from warnet.utils import (
    exponential_backoff,
    gen_config_dir,
    save_running_scenario,
    load_running_scenarios,
    remove_stopped_scenario,
    update_running_scenarios_file,
)

WARNET_SERVER_PORT = 9276

class Server():
    def __init__(self):
        self.basedir = os.environ.get("XDG_STATE_HOME")
        if self.basedir is None:
            # ~/.warnet/warnet.log
            self.basedir = os.path.join(os.environ["HOME"], ".warnet")
        else:
            # XDG_STATE_HOME / warnet / warnet.log
            self.basedir = os.path.join(self.basedir, "warnet")


        self.app = Flask(__name__)
        self.jsonrpc = JSONRPC(self.app, "/api")
        self.setup_rpc()

        self.log_file_path = os.path.join(self.basedir, "warnet.log")
        self.logger = None
        self.setup_logging()


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
                StreamHandler(sys.stdout)
            ],
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        # Disable urllib3.connectionpool logging
        logging.getLogger("urllib3.connectionpool").setLevel(logging.CRITICAL)
        self.logger = logging.getLogger("warnet")

        def log_request():
            self.logger.debug(request.json)

        self.app.before_request(log_request)


    def setup_rpc(self):
        # Tanks
        self.jsonrpc.register(self.bcli)
        self.jsonrpc.register(self.debug_log)
        self.jsonrpc.register(self.messages)
        # Scenarios
        self.jsonrpc.register(self.list)
        self.jsonrpc.register(self.run)
        self.jsonrpc.register(self.stop_scenario)
        self.jsonrpc.register(self.list_running_scenarios)
        # Networks
        self.jsonrpc.register(self.up)
        self.jsonrpc.register(self.from_file)
        self.jsonrpc.register(self.down)
        # Debug
        self.jsonrpc.register(self.update_dns_seeder)
        self.jsonrpc.register(self.generate_compose)
        # Server
        self.jsonrpc.register(self.stop)


    def bcli(self, node: int, method: str, params: List[str] = [], network: str = "warnet") -> str:
        """
        Call bitcoin-cli on <node> <method> <params> in [network]
        """
        try:
            result = get_bitcoin_cli(network, node, method, params)
            return str(result)
        except Exception as e:
            raise Exception(f"{e}")


    def debug_log(self, network: str, node: int) -> str:
        """
        Fetch the Bitcoin Core debug log from <node>
        """
        try:
            result = get_bitcoin_debug_log(network, node)
            return str(result)
        except Exception as e:
            raise Exception(f"{e}")


    def messages(self, network: str, node_a: int, node_b: int) -> str:
        """
        Fetch messages sent between <node_a> and <node_b>.
        """
        try:
            messages = [
                msg for msg in get_messages(network, node_a, node_b) if msg is not None
            ]
            if not messages:
                return f"No messages found between {node_a} and {node_b}"

            messages_str_list = []

            for message in messages:
                # Check if 'time' key exists and its value is a number
                if not (message.get("time") and isinstance(message["time"], (int, float))):
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
            raise Exception(f"{e}")


    def list(self) -> List[str]:
        """
        List available scenarios in the Warnet Test Framework
        """
        try:
            sc = []
            for s in pkgutil.iter_modules(scenarios.__path__):
                m = pkgutil.resolve_name(f"scenarios.{s.name}")
                if hasattr(m, "cli_help"):
                    sc.append(f"{s.name.ljust(20)}, {m.cli_help()}")
            return sc
        except Exception as e:
            return [f"Exception {e}"]


    running_scenarios = defaultdict(dict)


    def run(self, scenario: str, additional_args: List[str], network: str = "warnet") -> str:
        config_dir = gen_config_dir(network)
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        scenario_path = os.path.join(base_dir, "scenarios", f"{scenario}.py")

        if not os.path.exists(scenario_path):
            return f"Scenario {scenario} not found at {scenario_path}."

        try:
            run_cmd = (
                [sys.executable, scenario_path] + additional_args + [f"--network={network}"]
            )
            self.logger.debug(f"Running {run_cmd}")

            with subprocess.Popen(
                run_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            ) as process:
                for line in process.stdout:
                    self.logger.info(line.decode().rstrip())

            save_running_scenario(scenario, process, config_dir)

            return f"Running scenario {scenario} in the background..."
        except Exception as e:
            self.logger.error(f"Exception occurred while running the scenario: {e}")
            return f"Exception {e}"


    def stop_scenario(self, pid: int, network: str = "warnet") -> str:

        def is_running(pid):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return False
            return True

        @exponential_backoff()
        def kill_process(pid):
            os.kill(pid, signal.SIGKILL)

        config_dir = gen_config_dir(network)
        running_scenarios = load_running_scenarios(config_dir)

        scenario = None
        for scenario_name, scenario_pid in running_scenarios.items():
            if scenario_pid == pid:
                scenario = scenario_name
                break
        if not scenario:
            return f"No active scenario found for PID {pid}."

        if not is_running(pid):
            return f"Scenario {scenario} with PID {pid} was found in file but is not running."

        # First try with SIGTERM
        os.kill(pid, signal.SIGTERM)
        time.sleep(5)
        # Then try SIGKILL with exponential backoff
        if is_running(pid):
            kill_process(pid)

        if is_running(pid):
            return f"Could not kill scenario {scenario} with pid {pid} using SIGKILL"

        remove_stopped_scenario(scenario, config_dir)
        return f"Stopped scenario {scenario} with PID {pid}."


    def list_running_scenarios(self, network: str = "warnet") -> Dict[str, int]:
        config_dir = gen_config_dir(network)
        running_scenarios = load_running_scenarios(config_dir)

        # Check if each PID is still running
        still_running = {}
        for scenario, pid in running_scenarios.items():
            try:
                os.kill(pid, 0)  # Will raise an error if the process doesn't exist
                still_running[scenario] = pid
            except OSError:
                pass

        # Update the file with only the still running scenarios
        update_running_scenarios_file(config_dir, still_running)

        return still_running


    def up(self, network: str = "warnet") -> str:
        wn = Warnet.from_network(network=network, tanks=False)

        def thread_start(wn):
            try:
                wn.docker_compose_up()
                # Update warnet from docker here to get ip addresses
                wn = Warnet.from_docker_env(network)
                wn.apply_network_conditions()
                wn.connect_edges()
                self.logger.info(
                    f"Resumed warnet named '{network}' from config dir {wn.config_dir}"
                )
            except Exception as e:
                self.logger.error(f"Exception {e}")

        threading.Thread(target=lambda: thread_start(wn)).start()
        return f"Resuming warnet..."


    def from_file(self, graph_file: str, force: bool = False, network: str = "warnet") -> str:
        """
        Run a warnet with topology loaded from a <graph_file>
        """
        config_dir = gen_config_dir(network)
        if config_dir.exists():
            if force:
                shutil.rmtree(config_dir)
            else:
                return f"Config dir {config_dir} already exists, not overwriting existing warnet without --force"
        wn = Warnet.from_graph_file(graph_file, config_dir, network)

        def thread_start(wn):
            try:
                wn.write_bitcoin_confs()
                wn.write_docker_compose()
                wn.write_prometheus_config()
                wn.docker_compose_build_up()
                wn.generate_zone_file_from_tanks()
                wn.apply_zone_file()
                wn.apply_network_conditions()
                wn.connect_edges()
                self.logger.info(
                    f"Created warnet named '{network}' from graph file {graph_file}"
                )
            except Exception as e:
                self.logger.error(f"Exception {e}")

        threading.Thread(target=lambda: thread_start(wn)).start()
        return f"Starting warnet network named '{network}' with the following parameters:\n{wn}"


    def down(self, network: str = "warnet") -> str:
        """
        Stop all docker containers in <network>.
        """
        try:
            _ = compose_down(network)
            return "Stopping warnet"
        except Exception as e:
            return f"Exception {e}"


    def update_dns_seeder(self, graph_file: str, network: str = "warnet") -> str:
        try:
            config_dir = gen_config_dir(network)
            wn = Warnet.from_graph_file(graph_file, config_dir, network)
            wn.generate_zone_file_from_tanks()
            wn.apply_zone_file()
            with open(wn.zone_file_path, "r") as f:
                zone_file = f.read()

            return f"DNS seeder update using zone file:\n{zone_file}"
        except Exception as e:
            return f"DNS seeder not updated due to exception: {e}"


    def generate_compose(self, graph_file: str, network: str = "warnet") -> str:
        """
        Generate the docker compose file for a graph file and return import
        """
        config_dir = gen_config_dir(network)
        if config_dir.exists():
            return (
                f"Config dir {config_dir} already exists, not overwriting existing warnet"
            )
        wn = Warnet.from_graph_file(graph_file, config_dir, network)
        wn.write_bitcoin_confs()
        wn.write_docker_compose()
        docker_compose_path = wn.config_dir / "docker-compose.yml"
        with open(docker_compose_path, "r") as f:
            return f.read()


    def stop(self) -> str:
        """
        Stop warnet.
        """
        os.kill(os.getppid(), signal.SIGTERM)
        return "Stopping warnet server..."


def run_server():
    # https://flask.palletsprojects.com/en/2.3.x/api/#flask.Flask.run
    # "If the debug flag is set the server will automatically reload
    # for code changes and show a debugger in case an exception happened."
    Server().app.run(host="0.0.0.0", port=WARNET_SERVER_PORT, debug=False)


if __name__ == "__main__":
    run_server()
