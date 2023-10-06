import logging
import os
import pkgutil
import shutil
import signal
import subprocess
import sys
import threading
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
    gen_config_dir,
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

        self.running_scenarios = []

        self.app = Flask(__name__)
        self.jsonrpc = JSONRPC(self.app, "/api")
        self.setup_rpc()

        self.log_file_path = os.path.join(self.basedir, "warnet.log")
        self.logger: logging.Logger
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
        self.jsonrpc.register(self.info)
        self.jsonrpc.register(self.status)
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


    def list(self) -> List[tuple]:
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
            return [f"Exception {e}"]


    def run(self, scenario: str, additional_args: List[str], network: str = "warnet") -> str:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        scenario_path = os.path.join(base_dir, "scenarios", f"{scenario}.py")

        if not os.path.exists(scenario_path):
            return f"Scenario {scenario} not found at {scenario_path}."

        try:
            run_cmd = [sys.executable, scenario_path] + additional_args + [f"--network={network}"]
            self.logger.debug(f"Running {run_cmd}")

            proc = subprocess.Popen(
                run_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            def proc_logger():
                for line in proc.stdout:
                    self.logger.info(line.decode().rstrip())
            t = threading.Thread(target=lambda: proc_logger())
            t.daemon = True
            t.start()

            self.running_scenarios.append({
                "pid": proc.pid,
                "cmd": f"{scenario} {' '.join(additional_args)}",
                "proc": proc,
                "network": network,
            })

            return f"Running scenario {scenario} with PID {proc.pid} in the background..."
        except Exception as e:
            self.logger.error(f"Exception occurred while running the scenario: {e}")
            return f"Exception {e}"


    def stop_scenario(self, pid: int) -> str:
        matching_scenarios = [sc for sc in self.running_scenarios if sc["pid"] == pid]
        if matching_scenarios:
            matching_scenarios[0]["proc"].terminate() # sends SIGTERM
            # Remove from running list
            self.running_scenarios = [sc for sc in self.running_scenarios if sc["pid"] != pid]
            return f"Stopped scenario with PID {pid}."
        else:
            return f"Could not find scenario with PID {pid}."


    def list_running_scenarios(self) -> List[Dict]:
        return [{
            "pid": sc["pid"],
            "cmd": sc["cmd"],
            "active": sc["proc"].poll() is None,
            "network": sc["network"],
        } for sc in self.running_scenarios]


    def up(self, network: str = "warnet") -> str:
        wn = Warnet.from_network(network)

        def thread_start(wn):
            try:
                wn.docker_compose_up()
                # Update warnet from docker here to get ip addresses
                wn = Warnet.from_network(network)
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
                # grep: disable-exporters
                # wn.write_prometheus_config()
                wn.write_fork_observer_config()
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


    def info(self, network: str = "warnet") -> str:
        """
        Get info about a warnet network named <network>
        """
        wn = Warnet.from_network(network)
        return f"{wn}"


    def status(self, network: str = "warnet") -> List[dict]:
        """
        Get running status of a warnet network named <network>
        """
        wn = Warnet.from_network(network)
        stats = []
        for tank in wn.tanks:
            status = tank.container.status if tank.container is not None else None
            stats.append({
            "container_name": tank.container_name,
            "status": status})
        return stats


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
    Server().app.run(host="0.0.0.0", port=WARNET_SERVER_PORT, debug=True)


if __name__ == "__main__":
    run_server()
