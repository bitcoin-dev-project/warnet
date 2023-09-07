from pathlib import Path

import click
from rich import print

from templates import TEMPLATES
from warnet.cli.rpc import rpc_call

EXAMPLE_GRAPH_FILE = TEMPLATES / "example.graphml"


@click.group(name="network")
def network():
    """Network commands"""


@network.command()
@click.argument("graph_file", default=EXAMPLE_GRAPH_FILE, type=click.Path())
@click.option("--force", default=False, is_flag=True, type=bool)
@click.option("--network", default="warnet", show_default=True)
def from_graph(
    graph_file: Path = EXAMPLE_GRAPH_FILE, force: bool = False, network: str = "warnet"
):
    """
    Create a warnet with topology loaded from a <graph_file> into <--network> (default: "warnet")
    """
    try:
        result = rpc_call(
            "network_from_graph",
            {"graph_file": str(graph_file), "force": force, "network": network},
        )
        print(result)
    except Exception as e:
        print(f"Error creating network: {e}")


@network.command()
@click.option("--network", default="warnet", show_default=True)
def up(network: str = "warnet"):
    """
    Run 'docker-compose up' on a warnet named <--network> (default: "warnet").
    """
    try:
        result = rpc_call("network_up", {"network": network})
        print(result)
    except Exception as e:
        print(f"Error creating network: {e}")


@network.command()
@click.option("--network", default="warnet", show_default=True)
def down(network: str = "warnet"):
    """
    Run 'docker-compose down on a warnet named <--network> (default: "warnet").
    """
    try:
        result = rpc_call("network_down", {"network": network})
        print(result)
    except Exception as e:
        print(f"Error running docker-compose down on network {network}: {e}")

