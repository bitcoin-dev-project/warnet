import os
import requests
from typing_extensions import Annotated
from typing import Optional, Any, Tuple, Dict, Union
from pathlib import Path

from jsonrpcclient import Ok, parse, request
import typer
from rich import print

from templates import TEMPLATES
from warnet.warnetd import WARNETD_PORT

EXAMPLE_GRAPH_FILE = TEMPLATES / "example.graphml"

cli = typer.Typer()
debug = typer.Typer()
cli.add_typer(debug, name="debug", help="Various warnet debug commands")

def rpc(rpc_method, params: Optional[Union[Dict[str, Any], Tuple[Any, ...]]]):
    payload = request(rpc_method, params)
    response = requests.post(f"http://localhost:{WARNETD_PORT}/api", json=payload)
    parsed = parse(response.json())

    if isinstance(parsed, Ok):
        return parsed.result
    else:
        print(parsed)
        raise Exception(parsed.message)


@cli.command()
def bcli(
    node: int,
    method: str,
    params: Annotated[Optional[list[str]], typer.Argument()] = None,
    network: str = "warnet",
):
    """
    Call bitcoin-cli <method> <params> on <node> in <--network>
    """
    try:
        result = rpc(
            "bcli",
            {"network": network, "node": node, "method": method, "params": params},
        )
        print(result)
    except Exception as e:
        print(f"bitcoin-cli {method} {params} failed on node {node}:\n{e}")


@cli.command()
def debug_log(node: int, network: str = "warnet"):
    """
    Fetch the Bitcoin Core debug log from <node> in <network>
    """
    try:
        result = rpc("debug_log", {"node": node, "network": network})
        print(result)
    except Exception as e:
        print(f"In our pursuit of knowledge from node {node}, we were thwarted: {e}")


@cli.command()
def messages(node_a: int, node_b: int, network: str = "warnet"):
    """
    Fetch messages sent between <node_a> and <node_b> in <network>
    """
    try:
        result = rpc(
            "messages", {"network": network, "node_a": node_a, "node_b": node_b}
        )
        print(result)
    except Exception as e:
        print(
            f"Amidst the fog of war, we failed to relay messages between strongholds {node_a} and {node_b}: {e}"
        )


@cli.command()
def list():
    """
    List available scenarios in the Warnet Test Framework
    """
    try:
        result = rpc("list", None)
        print(result)
    except Exception as e:
        print(f"Error listing scenarios: {e}")


@cli.command()
def run(scenario: str):
    """
    Run <scenario> from the Warnet Test Framework
    """
    try:
        res = rpc("run", {"scenario": scenario})
        print(res)
    except Exception as e:
        print(f"Error running scenario: {e}")


@debug.command()
def generate_compose(graph_file: str, network: str = "warnet"):
    """
    Generate the docker-compose file for a given <graph_file> and <--network> name and return it.
    """
    try:
        result = rpc("generate_compose", {"graph_file": graph_file, "network": network})
        print(result)
    except Exception as e:
        print(f"Error generating compose: {e}")

@cli.command()
def start(graph_file: Path = EXAMPLE_GRAPH_FILE, network: str = "warnet"):
    """
    Start a warnet with topology loaded from a <graph_file> into <--network> (default: "warnet")
    """
    try:
        result = rpc("from_file", {"graph_file": str(graph_file), "network": network})
        print(result)
    except Exception as e:
        print(f"Error creating network: {e}")


@cli.command()
def up(network: str = "warnet"):
    """
    Run 'docker-compose up' on a warnet named <--network> (default: "warnet").
    """
    try:
        result = rpc("up", {"network": network})
        print(result)
    except Exception as e:
        print(f"Error creating network: {e}")


@cli.command()
def down(network: str = "warnet"):
    """
    Run 'docker-compose down on a warnet named <--network> (default: "warnet").
    """
    try:
        result = rpc("down", {"network": network})
        print(result)
    except Exception as e:
        print(f"As we endeavored to cease operations, adversity struck: {e}")


@cli.command()
def stop():
    """
    Stop the warnetd daemon.
    """
    try:
        result = rpc("stop", None)
        print(result)
    except Exception as e:
        print(f"As we endeavored to cease operations, adversity struck: {e}")


if __name__ == "__main__":
    cli()
