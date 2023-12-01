import base64
from pathlib import Path

import click
from rich import print
from rich.console import Console
from rich.table import Table

from graphs import GRAPHS
from warnet.cli.rpc import rpc_call


DEFAULT_GRAPH_FILE = GRAPHS / "default.graphml"


def print_repr(wn: dict) -> None:
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
        print_repr(result)
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
def down(network: str):
    """
    Run 'docker compose down on a warnet named <--network> (default: "warnet").
    """
    try:
        result = rpc_call("network_down", {"network": network})
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
        print_repr(result)
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

        # Preprocess the data to add color for "running" status
        colored_result = []
        for item in result:
            if item[1] == "running":
                colored_item = [item[0], f"[green]{item[1]}[/green]"]
            else:
                colored_item = item
            colored_result.append(colored_item)

        # Create the table
        table = Table(show_header=True, header_style="bold")
        table.add_column("Container name")
        table.add_column("Status")

        # Add rows to the table
        for row in colored_result:
            table.add_row(*row)

        console = Console()
        console.print(table)

    except Exception as e:
        print(f"[red]Error getting status of network {network}: {e}[/red]")


@network.command()
@click.option("--network", default="warnet", show_default=True)
def export(network):
    """
    Export all data for sim-ln to subdirectory
    """
    try:
        result = rpc_call("network_export", {"network": network})
        print(result)
    except Exception as e:
        print(f"Error exporting network: {e}")
