import base64
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
def start(graph_file: Path, force: bool, network: str):
    """
    Start a warnet with topology loaded from a <graph_file> into <--network> (default: "warnet")
    """
    try:
        encoded_graph_file = ""
        with open(graph_file, "rb") as graph_file_buffer:
            encoded_graph_file = base64.b64encode(graph_file_buffer.read()).decode("utf-8")
        result = rpc_call(
            "network_from_file",
            {"graph_file": encoded_graph_file, "force": force, "network": network},
        )
        print(result)
    except Exception as e:
        print(f"Error creating network: {e}")


@network.command()
@click.option("--network", default="warnet", show_default=True)
def up(network: str):
    """
    Run 'docker compose up' on a warnet named <--network> (default: "warnet").
    """
    try:
        result = rpc_call("network_up", {"network": network})
        print(result)
    except Exception as e:
        print(f"Error creating network: {e}")


@network.command()
@click.option("--network", default="warnet", show_default=True)
@click.option('--persist', is_flag=True)
def down(network: str, persist: bool):
    """
    Run 'docker compose down on a warnet named <--network> (default: "warnet").
    """
    try:
        result = rpc_call("network_down", {"network": network, "persist": persist})
        print(result)
    except Exception as e:
        print(f"Error running docker compose down on network {network}: {e}")


@network.command()
@click.option("--network", default="warnet", show_default=True)
def info(network: str):
    """
    Get info about a warnet named <--network> (default: "warnet").
    """
    try:
        result = rpc_call("network_info", {"network": network})
        print(result)
    except Exception as e:
        print(f"Error getting info about network {network}: {e}")


@network.command()
@click.option("--network", default="warnet", show_default=True)
def status(network: str):
    """
    Get status of a warnet named <--network> (default: "warnet").
    """
    try:
        result = rpc_call("network_status", {"network": network})
        for tank in result:
            print(f"{tank['container_name']}: {tank['status']}")
    except Exception as e:
        print(f"Error getting status of network {network}: {e}")



@network.command()
@click.option("--network", default="warnet", show_default=True)
def export(network):
    """
    Export all data for sim-ln to subdirectory
    """
    try:
        result = rpc_call(
            "network_export", {"network": network}
        )
        print(result)
    except Exception as e:
        print(
            f"Error exporting network: {e}"
        )
