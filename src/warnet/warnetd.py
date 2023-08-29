import os
import pkgutil
import subprocess
import sys
from datetime import datetime
from daemon import DaemonContext
from jsonrpcserver import method, serve, Success, Error
import logging
from logging.handlers import RotatingFileHandler
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

# Determine the log file path based on XDG_STATE_HOME
xdg_state_home = os.environ.get('XDG_STATE_HOME', os.path.join(os.environ['HOME'], '.local', 'state'))
log_file_path = os.path.join(xdg_state_home, 'warnet', 'logfile.log')

# Ensure the directory exists
os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

logger = logging.getLogger('warnetd')
logger.setLevel(logging.DEBUG)
# Create a handler that writes log messages to a file, with a maximum
# log file size of 1 MB, keeping 3 backup old log files.
handler = RotatingFileHandler(log_file_path, maxBytes=1e6, backupCount=3)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


@method
def bcli(network: str, node: int, method: str, params: list[str] = []):
    """
    Call bitcoin-cli <method> <params> on <node> in [network]
    """
    try:
        result = get_bitcoin_cli(network, node, method, params)
        return Success(result)
    except Exception as e:
        return Error(f"{e}")


@method
def debug_log(network: str, node: int):
    """
    Fetch the Bitcoin Core debug log from <node>
    """
    try:
        result = get_bitcoin_debug_log(network, node)
        return Success(result)
    except Exception as e:
        return Error(f"{e}")


@method
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
        return Success(out)
    except Exception as e:
        return Error(f"{e}")


@method
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
        return Success(sc)
    except Exception as e:
        return Error(f"{e}")


@method
def run(scenario: str):
    """
    Run <scenario> from the Warnet Test Framework
    """
    try:
        # TODO: should accept network argument
        dir_path = os.path.dirname(os.path.realpath(__file__))
        mod_path = os.path.join(dir_path, '..', 'scenarios', f"{sys.argv[2]}.py")
        run_cmd = [sys.executable, mod_path] + sys.argv[3:]
        subprocess.run(run_cmd, shell=False)
        return Success(True)
    except Exception as e:
        return Error(f"{e}")


@method
def from_file(graph_file: str, network: str):
    """
    Run a warnet with topology loaded from a <graph_file>
    """
    try:
        wn = Warnet.from_graph_file(graph_file, network)
        wn.write_bitcoin_confs()
        wn.write_docker_compose()
        wn.write_prometheus_config()
        wn.docker_compose_up()
        wn.apply_network_conditions()
        wn.connect_edges()
        return Success(True)
    except Exception as e:
        return Error(f"{e}")


@method
def stop():
    """
    Stop all docker containers in <network>.
    """
    try:
        result = stop_network()
        return Success(result)
    except Exception as e:
        return Error(f"{e}")


@method
def wipe():
    """
    Stop and then erase all docker containers in <network>, and then the docker network itself.
    """
    try:
        stop_network()
        result = wipe_network()
        return Success(result)
    except Exception as e:
        return Error(f"{e}")


def server():
    """
    Run warnetd RPC server.
    """
    with DaemonContext( stdout=handler.stream, stderr=handler.stream):
        serve(port=WARNETD_PORT)


if __name__ == "__main__":
    server()
