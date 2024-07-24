import base64
import os
import sys

import click
from rich import print
from rich.console import Console
from rich.table import Table

from .rpc import rpc_call


@click.group(name="scenarios")
def scenarios():
    """Manage scenarios on a running network"""


@scenarios.command()
def available():
    """
    List available scenarios in the Warnet Test Framework
    """
    console = Console()
    result = rpc_call("scenarios_available", None)
    if not isinstance(result, list):  # Make mypy happy
        print(f"Error. Expected list but got {type(result)}: {result}")
        sys.exit(1)

    # Create the table
    table = Table(show_header=True, header_style="bold")
    table.add_column("Name")
    table.add_column("Description")

    for scenario in result:
        table.add_row(scenario[0], scenario[1])
    console.print(table)


@scenarios.command(context_settings={"ignore_unknown_options": True})
@click.argument("scenario", type=str)
@click.argument("additional_args", nargs=-1, type=click.UNPROCESSED)
@click.option("--network", default="warnet", show_default=True)
def run(scenario, network, additional_args):
    """
    Run <scenario> from the Warnet Test Framework on [network] with optional arguments
    """
    params = {
        "scenario": scenario,
        "additional_args": additional_args,
        "network": network,
    }
    print(rpc_call("scenarios_run", params))


@scenarios.command(context_settings={"ignore_unknown_options": True})
@click.argument("scenario_path", type=str)
@click.argument("additional_args", nargs=-1, type=click.UNPROCESSED)
@click.option("--name", type=str)
@click.option("--network", default="warnet", show_default=True)
def run_file(scenario_path, network, additional_args, name=""):
    """
    Run <scenario_path> from the Warnet Test Framework on [network] with optional arguments
    """
    if not scenario_path.endswith(".py"):
        print("Error. Currently only python scenarios are supported")
        sys.exit(1)
    scenario_name = name if name else os.path.splitext(os.path.basename(scenario_path))[0]
    scenario_base64 = ""
    with open(scenario_path, "rb") as f:
        scenario_base64 = base64.b64encode(f.read()).decode("utf-8")

    params = {
        "scenario_base64": scenario_base64,
        "scenario_name": scenario_name,
        "additional_args": additional_args,
        "network": network,
    }
    print(rpc_call("scenarios_run_file", params))


@scenarios.command()
def active():
    """
    List running scenarios "name": "pid" pairs
    """
    console = Console()
    result = rpc_call("scenarios_list_running", {})
    if not result:
        print("No scenarios running")
        return
    assert isinstance(result, list)  # Make mypy happy

    table = Table(show_header=True, header_style="bold")
    for key in result[0].keys():  # noqa: SIM118
        table.add_column(key.capitalize())

    for scenario in result:
        table.add_row(*[str(scenario[key]) for key in scenario])

    console.print(table)


@scenarios.command()
@click.argument("pid", type=int)
def stop(pid: int):
    """
    Stop scenario with PID <pid> from running
    """
    params = {"pid": pid}
    print(rpc_call("scenarios_stop", params))
