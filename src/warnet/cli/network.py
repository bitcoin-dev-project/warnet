import base64  # noqa: I001
from pathlib import Path

import click
import json
from rich import print
from rich.console import Console
from rich.table import Table
from .rpc import rpc_call  # noqa: I001

from warnet.graphs import GRAPHS  # noqa: I001

DEFAULT_GRAPH_FILE = GRAPHS / "default.graphml"


def print_repr(wn: dict) -> None:
    if not isinstance(wn, dict):
        print("Error, cannot print_repr of non-dict")
        return
    console = Console()

    # Warnet table
    warnet_table = Table(show_header=True, header_style="bold")
    for header in wn["warnet_headers"]:
        warnet_table.add_column(header)
    for row in wn["warnet"]:
        warnet_table.add_row(*[str(cell) for cell in row])

    # Tank table
    tank_table = Table(show_header=True, header_style="bold")
    for header in wn["tank_headers"]:
        tank_table.add_column(header)
    for row in wn["tanks"]:
        tank_table.add_row(*[str(cell) for cell in row])

    console.print("Warnet:")
    console.print(warnet_table)
    console.print("\nTanks:")
    console.print(tank_table)


@click.group(name="network")
def network():
    """Network commands"""


@network.command()
@click.argument("graph_file", default=DEFAULT_GRAPH_FILE, type=click.Path())
@click.option("--force", default=False, is_flag=True, type=bool)
@click.option("--network", default="warnet", show_default=True)
def start(graph_file: Path, force: bool, network: str):
    """
    Start a warnet with topology loaded from a <graph_file> into [network]
    """
    try:
        encoded_graph_file = ""
        with open(graph_file, "rb") as graph_file_buffer:
            encoded_graph_file = base64.b64encode(graph_file_buffer.read()).decode("utf-8")
    except Exception as e:
        print(f"Error encoding graph file: {e}")
        return

    result = rpc_call(
        "network_from_file",
        {"graph_file": encoded_graph_file, "force": force, "network": network},
    )
    assert isinstance(result, dict)
    print_repr(result)


@network.command()
@click.option("--network", default="warnet", show_default=True)
def up(network: str):
    """
    Bring up a previously-stopped warnet named [network]
    """
    print(rpc_call("network_up", {"network": network}))


@network.command()
@click.option("--network", default="warnet", show_default=True)
def down(network: str):
    """
    Bring down a running warnet named [network]
    """

    running_scenarios = rpc_call("scenarios_list_running", {})
    assert isinstance(running_scenarios, list)
    if running_scenarios:
        for scenario in running_scenarios:
            pid = scenario.get("pid")
            if pid:
                try:
                    params = {"pid": pid}
                    rpc_call("scenarios_stop", params)
                except Exception as e:
                    print(
                        f"Exception when stopping scenario: {scenario} with PID {scenario.pid}: {e}"
                    )
                    print("Continuing with shutdown...")
                    continue
    print(rpc_call("network_down", {"network": network}))


@network.command()
@click.option("--network", default="warnet", show_default=True)
def info(network: str):
    """
    Get info about a warnet named [network]
    """
    result = rpc_call("network_info", {"network": network})
    assert isinstance(result, dict), "Result is not a dict"  # Make mypy happy
    print_repr(result)


@network.command()
@click.option("--network", default="warnet", show_default=True)
def status(network: str):
    """
    Get status of a warnet named [network]
    """
    result = rpc_call("network_status", {"network": network})
    assert isinstance(result, list), "Result is not a list"  # Make mypy happy
    for tank in result:
        lightning_status = ""
        circuitbreaker_status = ""
        if "lightning_status" in tank:
            lightning_status = f"\tLightning: {tank['lightning_status']}"
        if "circuitbreaker_status" in tank:
            circuitbreaker_status = f"\tCircuit Breaker: {tank['circuitbreaker_status']}"
        print(
            f"Tank: {tank['tank_index']} \tBitcoin: {tank['bitcoin_status']}{lightning_status}{circuitbreaker_status}"
        )


@network.command()
@click.option("--network", default="warnet", show_default=True)
def connected(network: str):
    """
    Indicate whether the all of the edges in the gaph file are connected in [network]
    """
    print(rpc_call("network_connected", {"network": network}))


@network.command()
@click.option("--network", default="warnet", show_default=True)
@click.option("--activity", type=str)
@click.option("--exclude", type=str, default="[]")
def export(network: str, activity: str, exclude: str):
    """
    Export all [network] data for a "simln" service running in a container
    on the network. Optionally add JSON string [activity] to simln config.
    Optionally provide a list of tank indexes to [exclude].
    Returns True on success.
    """
    exclude = json.loads(exclude)
    print(
        rpc_call("network_export", {"network": network, "activity": activity, "exclude": exclude})
    )
