import typer
from typing_extensions import Annotated
from typing import Optional
import logging
import os
import pkgutil
import subprocess
import sys
from datetime import datetime
from templates import TEMPLATES
import scenarios
from warnet.warnet import Warnet
from warnet.client import (
    get_bitcoin_cli,
    get_bitcoin_debug_log,
    get_messages,
    stop_network,
    wipe_network
)

EXAMPLE_GRAPH_FILE = TEMPLATES / "example.graphml"

warnet_app = typer.Typer()
run_app = typer.Typer()
warnet_app.add_typer(run_app, name="start", help="Start a warnet. `warnet start --help` for more info")

logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=logging.INFO
)

@warnet_app.command()
def bcli(network: str, node: int, method: str, params: Annotated[Optional[list[str]], typer.Argument()] = None):
    """
    Call bitcoin-cli <method> <params> on <node> in <network>
    """
    try:
        result = get_bitcoin_cli(network, node, method, params)
        typer.echo(result)
    except Exception as e:
        typer.echo(f"In our quest to command node {node}, we encountered resistance: {e}")


@warnet_app.command()
def debug_log(network: str, node: int):
    """
    Fetch the Bitcoin Core debug log from <node> in <network>
    """
    try:
        result = get_bitcoin_debug_log(network, node)
        typer.echo(result)
    except Exception as e:
        typer.echo(f"In our pursuit of knowledge from node {node}, we were thwarted: {e}")

@warnet_app.command()
def messages(network: str, node_a: int, node_b: int):
    """
    Fetch messages sent between <node_a> and <node_b> in <network>
    """
    try:
        messages = get_messages(network, node_a, node_b)
        out = ""
        for m in messages:
            timestamp = datetime.utcfromtimestamp(m["time"] / 1e6).strftime('%Y-%m-%d %H:%M:%S')
            direction = ">>>" if m["outbound"] else "<<<"
            body = ""
            if "body" in m:
                body = m["body"]
            out = out + f"{timestamp} {direction} {m['msgtype']} {body}\n"
        typer.echo(out)
    except Exception as e:
        typer.echo(f"Amidst the fog of war, we failed to relay messages between strongholds {node_a} and {node_b}: {e}")

@warnet_app.command()
def list():
    """
    List available scenarios in the Warnet Test Framework
    """
    for s in pkgutil.iter_modules(scenarios.__path__):
        m = pkgutil.resolve_name(f"scenarios.{s.name}")
        if hasattr(m, "cli_help"):
            print(s.name.ljust(20),m.cli_help())

@warnet_app.command()
def run(scenario: str):
    """
    Run <scenario> from the Warnet Test Framework
    """
    # TODO: should accept network argument
    dir_path = os.path.dirname(os.path.realpath(__file__))
    mod_path = os.path.join(dir_path, '..', 'scenarios', f"{sys.argv[2]}.py")
    run_cmd = [sys.executable, mod_path] + sys.argv[3:]
    subprocess.run(run_cmd, shell=False)

@run_app.command()
def from_file(graph_file: str, network: str = "warnet"):
    """
    Run a warnet with topology loaded from a <graph_file> into [network] (default: "warnet")
    """
    wn = Warnet.from_graph_file(graph_file, network)
    wn.write_bitcoin_confs()
    wn.write_docker_compose()
    wn.write_prometheus_config()
    wn.docker_compose_up()
    wn.generate_zone_file_from_tanks()
    wn.apply_zone_file()
    wn.apply_network_conditions()
    wn.connect_edges()

@warnet_app.command()
def sync_dns_seed(network: str = "warnet"):
    wn = Warnet.from_docker_env(network)
    wn.generate_zone_file_from_tanks()
    wn.apply_zone_file()

@warnet_app.command()
def stop():
    """
    Stop all docker containers in [network] (default: "warnet").
    """
    try:
        result = stop_network()
        typer.echo(result)
    except Exception as e:
        typer.echo(f"As we endeavored to cease operations, adversity struck: {e}")

@warnet_app.command()
def wipe():
    """
    Stop and then erase all docker containers in [network] (default: "warnet"), and then the docker network itself.
    """
    try:
        result = stop_network()
        typer.echo(result)
    except Exception as e:
        typer.echo(f"Error stopping containers: {e}")
    try:
        result = wipe_network()
        typer.echo(result)
    except Exception as e:
        typer.echo(f"Error wiping network: {e}")

if __name__ == "__main__":
    warnet_app()
