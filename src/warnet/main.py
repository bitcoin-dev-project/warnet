from jsonrpcclient import Ok, parse, request
import requests
import typer
from typing_extensions import Annotated
from typing import Optional
from flask import jsonify
import requests
from templates import TEMPLATES
from warnet.warnetd import WARNETD_PORT

EXAMPLE_GRAPH_FILE = TEMPLATES / "example.graphml"


def rpc(rpc_method, params: [] = []):
    payload = request(rpc_method, params)
    response = requests.post(f"http://localhost:{WARNETD_PORT}/api", json=payload)
    parsed = parse(response.json())

    if isinstance(parsed, Ok):
        return parsed.result
    else:
        print(parsed)
        raise Exception(parsed.message)


cli = typer.Typer()


@cli.command()
def bcli(
    network: str,
    node: int,
    method: str,
    params: Annotated[Optional[list[str]], typer.Argument()] = None,
):
    """
    Call bitcoin-cli <method> <params> on <node> in <network>
    """
    try:
        result = rpc("get_bitcoin_cli", [network, node, method, params])
        typer.echo(result)
    except Exception as e:
        typer.echo(
            f"In our quest to command node {node}, we encountered resistance: {e}"
        )


@cli.command()
def debug_log(network: str, node: int):
    """
    Fetch the Bitcoin Core debug log from <node> in <network>
    """
    try:
        result = rpc("get_bitcoin_debug_log", [network,node])
        typer.echo(result)
    except Exception as e:
        typer.echo(
            f"In our pursuit of knowledge from node {node}, we were thwarted: {e}"
        )


@cli.command()
def messages(network: str, node_a: int, node_b: int):
    """
    Fetch messages sent between <node_a> and <node_b> in <network>
    """
    try:
        result = rpc("get_messages", [network, node_a, node_b])
        typer.echo(result)
    except Exception as e:
        typer.echo(
            f"Amidst the fog of war, we failed to relay messages between strongholds {node_a} and {node_b}: {e}"
        )


@cli.command()
def list():
    """
    List available scenarios in the Warnet Test Framework
    """
    try:
        result = rpc("list")
        typer.echo(result)
    except Exception as e:
        typer.echo(f"Error listing scenarios: {e}")


@cli.command()
def run(scenario: str):
    """
    Run <scenario> from the Warnet Test Framework
    """
    try:
        res = rpc("run", [scenario])
        typer.echo(res)
    except Exception as e:
        typer.echo(f"Error running scenario: {e}")


@cli.command()
def from_file(graph_file, network: str="warnet"):
    """
    Run a warnet with topology loaded from a <graph_file> into [network] (default: "warnet")
    """
    try:
        result = rpc("from_file", [graph_file, network])
        typer.echo(result)
    except Exception as e:
        typer.echo(f"Error creating network: {e}")


@cli.command()
def stop():
    """
    Stop all docker containers in [network] (default: "warnet").
    """
    try:
        result = rpc("stop")
        typer.echo(result)
    except Exception as e:
        typer.echo(f"As we endeavored to cease operations, adversity struck: {e}")


@cli.command()
def wipe():
    """
    Stop and then erase all docker containers in [network] (default: "warnet"), and then the docker network itself.
    """
    try:
        result = rpc("wipe_network")
        typer.echo(result)
    except Exception as e:
        typer.echo(f"Error wiping network: {e}")


@cli.command()
def stop_daemon():
    """
    Stop the warnetd daemon.
    """
    try:
        result = rpc("stop_daemon")
        typer.echo(result)
    except Exception as e:
        typer.echo(f"As we endeavored to cease operations, adversity struck: {e}")



if __name__ == "__main__":
    cli()
