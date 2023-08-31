import argparse
import logging
import os
import pkgutil
import signal
import subprocess
import sys
import threading
from datetime import datetime
from logging.handlers import RotatingFileHandler

from flask import Flask
from flask_jsonrpc.app import JSONRPC

import scenarios
from warnet.warnet import Warnet
from warnet.client import (
    get_bitcoin_cli,
    get_bitcoin_debug_log,
    get_messages,
    stop_network,
    wipe_network,
)

WARNETD_PORT = 9276
continue_running = True

app = Flask(__name__)
jsonrpc = JSONRPC(app, "/api")

# Determine the log file path based on XDG_STATE_HOME
xdg_state_home = os.environ.get(
    "XDG_STATE_HOME", os.path.join(os.environ["HOME"], ".local", "state")
)
log_file_path = os.path.join(xdg_state_home, "warnet", "warnet.log")

# Ensure the directory exists
os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

# Configure root logger
logging.basicConfig(
    level=logging.DEBUG,
    handlers=[
        RotatingFileHandler(
            log_file_path, maxBytes=16_000_000, backupCount=3, delay=True
        )
    ],
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
# Disable urllib3.connectionpool logging
logging.getLogger("urllib3.connectionpool").setLevel(logging.CRITICAL)

logger = logging.getLogger("warnetd")


@jsonrpc.method("bcli")
def bcli(node: int, method: str, params: list[str] = [], network: str = "warnet"):
    """
    Call bitcoin-cli on <node> <method> <params> in [network]
    """
    try:
        result = get_bitcoin_cli(network, node, method, params)
        return result
    except Exception as e:
        raise Exception(f"{e}")


@jsonrpc.method("debug_log")
def debug_log(network: str, node: int):
    """
    Fetch the Bitcoin Core debug log from <node>
    """
    try:
        result = get_bitcoin_debug_log(network, node)
        return result
    except Exception as e:
        raise Exception(f"{e}")


@jsonrpc.method("messages")
def messages(network: str, node_a: int, node_b: int):
    """
    Fetch messages sent between <node_a> and <node_b>.
    """
    try:
        messages = get_messages(network, node_a, node_b)
        out = ""
        for m in messages:
            timestamp = datetime.utcfromtimestamp(m["time"] / 1e6).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            direction = ">>>" if m["outbound"] else "<<<"
            body = ""
            if "body" in m:
                body = m["body"]
            out = out + f"{timestamp} {direction} {m['msgtype']} {body}\n"
        return out
    except Exception as e:
        raise Exception(f"{e}")


@jsonrpc.method("list")
def list() -> list[str]:
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


@jsonrpc.method("run")
def run(scenario: str, network: str = "warnet") -> str:
    """
    Run <scenario> from the Warnet Test Framework
    """
    try:
        # TODO: should handle network argument
        dir_path = os.path.dirname(os.path.realpath(__file__))
        mod_path = os.path.join(dir_path, "..", "scenarios", f"{sys.argv[2]}.py")
        run_cmd = [sys.executable, mod_path] + sys.argv[3:]
        subprocess.Popen(run_cmd, shell=False)
        # TODO: We could here use python-prctl to give the background process
        # a name prefixed with "warnet"? Might only work on linux...
        return f"Running scenario {scenario} in the background..."
    except Exception as e:
        return f"Exception {e}"


@jsonrpc.method()
def from_file(graph_file: str, network: str = "warnet") -> str:
    """
    Run a warnet with topology loaded from a <graph_file>
    """
    wn = Warnet.from_graph_file(graph_file, network)

    def thread_start(wn):
        try:
            wn.write_bitcoin_confs()
            wn.write_docker_compose()
            wn.write_prometheus_config()
            wn.docker_compose_up()
            wn.apply_network_conditions()
            wn.connect_edges()
            logger.info(f"Created warnet named '{network}' from graph file {graph_file}")
        except Exception as e:
            logger.error(f"Exception {e}")

    threading.Thread(target=lambda: thread_start(wn)).start()
    return f"Starting warnet network named '{network}' with the following parameters:\n{wn}"


@jsonrpc.method()
def generate_compose(graph_file: str, network: str = "warnet") -> str:
    """
    Generate the docker compose file for a graph file and return import
    """
    wn = Warnet.from_graph_file(graph_file, network)
    wn.write_bitcoin_confs()
    wn.write_docker_compose()
    docker_compose_path = wn.tmpdir / "docker-compose.yml"
    with open(docker_compose_path, "r") as f:
        return f.read()


@jsonrpc.method("stop")
def stop(network: str = "warnet") -> str:
    """
    Stop all docker containers in <network>.
    """
    try:
        _ = stop_network(network)
        return "Stopping warnet"
    except Exception as e:
        return f"Exception {e}"


@jsonrpc.method("wipe")
def wipe(network: str = "warnet") -> str:
    """
    Stop and then erase all docker containers in <network>, and then the docker network itself.
    """
    try:
        wipe_network(network)
        return "Stopping and wiping warnet"
    except Exception as e:
        return f"Exception {e}"


@jsonrpc.method("stop_daemon")
def stop_daemon() -> str:
    """
    Stop the daemon.
    """
    os.kill(os.getppid(), signal.SIGTERM)
    return "Stopping daemon..."


def run_gunicorn():
    """
    Run the RPC server using gunicorn WSGI HTTP server
    """
    parser = argparse.ArgumentParser(description='Run the Warnet RPC server.')
    parser.add_argument('--no-daemon', default=False, action='store_true', help='Run server in the foreground instead of daemon mode.')
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
    if not args.no_daemon:
        command.extend([
            "--daemon",
            "--access-logfile",
            log_file_path,
            "--error-logfile",
            log_file_path,
        ])
 
    subprocess.run(command)


if __name__ == "__main__":
    run_gunicorn()
