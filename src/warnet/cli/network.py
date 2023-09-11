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
def start(
    graph_file: Path = EXAMPLE_GRAPH_FILE, force: bool = False, network: str = "warnet"
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
@click.argument("graph_file", default=EXAMPLE_GRAPH_FILE, type=click.Path())
@click.option("--network", default="warnet", show_default=True)
def build(graph_file: Path = EXAMPLE_GRAPH_FILE, network: str = "warnet"):
    """
    Run 'docker-compose build' on a warnet named <--network> (default: "warnet").
    """
    try:
        result = rpc_call("build_from_graph_file", {"graph_file": str(graph_file), "network": network})
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
        result = rpc_call("up", {"network": network})
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
        result = rpc_call("down", {"network": network})
        print(result)
    except Exception as e:
        print(f"Error running docker-compose down on network {network}: {e}")

