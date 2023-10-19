from pathlib import Path

import click
from rich import print

from graphs import GRAPHS
from warnet.cli.rpc import rpc_call

DEFAULT_GRAPH_FILE = GRAPHS / "default.graphml"

@click.group(name="network")
def network():
    """Network commands"""

@network.command()
@click.argument("graph_file", default=DEFAULT_GRAPH_FILE, type=click.Path())
@click.option("--force", default=False, is_flag=True, type=bool)
@click.option("--network", default="warnet", show_default=True)
def start(
    graph_file: Path = DEFAULT_GRAPH_FILE, force: bool = False, network: str = "warnet"
):
    """
    Start a warnet with topology loaded from a <graph_file> into <--network> (default: "warnet")
    """
    try:
        result = rpc_call(
            "from_file",
            {"graph_file": str(graph_file), "force": force, "network": network},
        )
        print(result)
    except Exception as e:
        print(f"Error creating network: {e}")


@network.command()
@click.option("--network", default="warnet", show_default=True)
def up(network: str = "warnet"):
    """
    Run 'docker compose up' on a warnet named <--network> (default: "warnet").
    """
    try:
        result = rpc_call("up", {"network": network})
        print(result)
    except Exception as e:
        print(f"Error creating network: {e}")


@network.command()
@click.option("--network", default="warnet", show_default=True)
def down(network: str = "warnet"):
    """
    Run 'docker compose down on a warnet named <--network> (default: "warnet").
    """
    try:
        result = rpc_call("down", {"network": network})
        print(result)
    except Exception as e:
        print(f"Error running docker compose down on network {network}: {e}")


@network.command()
@click.option("--network", default="warnet", show_default=True)
def info(network: str = "warnet"):
    """
    Get info about a warnet named <--network> (default: "warnet").
    """
    try:
        result = rpc_call("info", {"network": network})
        print(result)
    except Exception as e:
        print(f"Error getting info about network {network}: {e}")


@network.command()
@click.option("--network", default="warnet", show_default=True)
def status(network: str = "warnet"):
    """
    Get status of a warnet named <--network> (default: "warnet").
    """
    try:
        result = rpc_call("status", {"network": network})
        for tank in result:
            print(f"{tank['container_name']}: {tank['status']}")
    except Exception as e:
        print(f"Error getting status of network {network}: {e}")

