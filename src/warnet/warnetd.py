import argparse
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
from flask import Flask
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

WARNETD_PORT = 9276

# Determine the log file path:
basedir = os.environ.get("XDG_STATE_HOME")
if basedir is None:
    # ~/.warnet/warnet.log
    basedir = os.path.join(os.environ["HOME"], ".warnet")
else:
    # XDG_STATE_HOME / warnet / warnet.log
    basedir = os.path.join(basedir, "warnet")
LOG_FILE_PATH = os.path.join(basedir, "warnet.log")

# Ensure the directory exists
os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)

# Configure root logger
logging.basicConfig(
    level=logging.DEBUG,
    handlers=[
        RotatingFileHandler(
            LOG_FILE_PATH, maxBytes=16_000_000, backupCount=3, delay=True
        ),
        StreamHandler(sys.stdout)
    ],
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
# Disable urllib3.connectionpool logging
logging.getLogger("urllib3.connectionpool").setLevel(logging.CRITICAL)
logger = logging.getLogger("warnetd")

app = Flask(__name__)
jsonrpc = JSONRPC(app, "/api")


@jsonrpc.method("bcli")
def bcli(
    node: int, method: str, params: List[str] = [], network: str = "warnet"
) -> str:
    """
    Call bitcoin-cli on <node> <method> <params> in [network]
    """
    try:
        result = get_bitcoin_cli(network, node, method, params)
        return str(result)
    except Exception as e:
        raise Exception(f"{e}")


@jsonrpc.method("debug_log")
def debug_log(network: str, node: int) -> str:
    """
    Fetch the Bitcoin Core debug log from <node>
    """
    try:
        result = get_bitcoin_debug_log(network, node)
        return str(result)
    except Exception as e:
        raise Exception(f"{e}")


@jsonrpc.method("messages")
def messages(network: str, node_a: int, node_b: int) -> str:
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


@jsonrpc.method("list")
def list() -> List[str]:
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


@jsonrpc.method("run")
def run(scenario: str, additional_args: List[str], network: str = "warnet") -> str:
    config_dir = gen_config_dir(network)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    scenario_path = os.path.join(base_dir, "scenarios", f"{scenario}.py")

    if not os.path.exists(scenario_path):
        return f"Scenario {scenario} not found at {scenario_path}."

    try:
        run_cmd = (
            [sys.executable, scenario_path] + additional_args + [f"--network={network}"]
        )
        logger.debug(f"Running {run_cmd}")
        process = subprocess.Popen(run_cmd, shell=False, preexec_fn=os.setsid)

        save_running_scenario(scenario, process, config_dir)

        return f"Running scenario {scenario} in the background..."
    except Exception as e:
        logger.error(f"Exception occurred while running the scenario: {e}")
        return f"Exception {e}"


@jsonrpc.method("stop_scenario")
def stop_scenario(pid: int, network: str = "warnet") -> str:

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


@jsonrpc.method("list_running_scenarios")
def list_running_scenarios(network: str = "warnet") -> Dict[str, int]:
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


@jsonrpc.method("up")
def up(network: str = "warnet") -> str:
    wn = Warnet.from_network(network=network)

    def thread_start(wn):
        try:
            wn.docker_compose_up()
            # Update warnet from docker here to get ip addresses
            wn = Warnet.from_docker_env(network)
            wn.apply_network_conditions()
            wn.connect_edges()
            logger.info(
                f"Resumed warnet named '{network}' from config dir {wn.config_dir}"
            )
        except Exception as e:
            logger.error(f"Exception {e}")

    threading.Thread(target=lambda: thread_start(wn)).start()
    return f"Resuming warnet..."


@jsonrpc.method()
def from_file(graph_file: str, force: bool = False, network: str = "warnet") -> str:
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
            logger.info(
                f"Successfully created warnet named '{network}' from graph file {graph_file}"
            )
        except Exception as e:
            logger.error(f"Error creating warnet named '{network}': {e}")

    threading.Thread(target=lambda: thread_start(wn)).start()
    return f"Starting warnet network named '{network}' with the following parameters:\n{wn}"


@jsonrpc.method()
def build_from_graph_file(graph_file: str, force: bool = False, network: str = "warnet") -> str:
    config_dir = gen_config_dir(network)
    if config_dir.exists():
        if force:
            shutil.rmtree(config_dir)
        else:
            return f"Config dir {config_dir} already exists, not overwriting existing warnet without --force"
    res = False
    try:
        wn = Warnet.from_graph_file(graph_file, config_dir, network)
        wn.write_bitcoin_confs()
        wn.write_docker_compose()
        wn.write_prometheus_config()
        res = wn.docker_compose_build()
    except Exception as e:
        logger.error(f"Exception {e}")
    if res:
        return f"Build warnet network named '{network}' with the following parameters:\n{wn}"
    else:
        return "Failed to build from graph file. Check logs for more info."


@jsonrpc.method()
def update_dns_seeder(graph_file: str, network: str = "warnet") -> str:
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


@jsonrpc.method()
def generate_compose(graph_file: str, network: str = "warnet") -> str:
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


@jsonrpc.method("down")
def down(network: str = "warnet") -> str:
    """
    Stop all docker containers in <network>.
    """
    try:
        _ = compose_down(network)
        return "Stopping warnet"
    except Exception as e:
        return f"Exception {e}"


@jsonrpc.method("stop")
def stop() -> str:
    """
    Stop warnetd.
    """
    os.kill(os.getppid(), signal.SIGTERM)
    return "Stopping daemon..."


def run_gunicorn():
    """
    Run the RPC server using gunicorn WSGI HTTP server
    """
    parser = argparse.ArgumentParser(description="Run the Warnet RPC server.")
    parser.add_argument(
        "--daemon",
        default=False,
        action="store_true",
        help="Run server in the background.",
    )
    args = parser.parse_args()

    command = [
        "gunicorn",
        "-w",
        "4",
        f"-b :{WARNETD_PORT}",
        "--log-level",
        "debug",
        "warnet.warnetd:app",
    ]

    # If in daemon mode, log to file and add daemon argument
    if args.daemon:
        command.extend(
            [
                "--daemon",
                "--access-logfile",
                LOG_FILE_PATH,
                "--error-logfile",
                LOG_FILE_PATH,
            ]
        )

    subprocess.run(command)


if __name__ == "__main__":
    run_gunicorn()
