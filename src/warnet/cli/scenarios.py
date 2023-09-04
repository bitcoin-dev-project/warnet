import click
from rich import print

from templates import TEMPLATES
from warnet.cli.rpc import rpc_call

EXAMPLE_GRAPH_FILE = TEMPLATES / "example.graphml"


@click.group(name="scenarios")
def scenarios():
    """Scenario commands"""


@scenarios.command()
def list():
    """
    List available scenarios in the Warnet Test Framework
    """
    try:
        result = rpc_call("list", None)
        print(result)
    except Exception as e:
        print(f"Error listing scenarios: {e}")


@scenarios.command(context_settings={"ignore_unknown_options": True})
@click.argument("scenario", type=str)
@click.argument("additional_args", nargs=-1, type=click.UNPROCESSED)
@click.option("--network", default="warnet", show_default=True)
def run(scenario, network, additional_args):
    """
    Run <scenario> from the Warnet Test Framework on <--network> with optional arguments
    """
    try:
        params = {"scenario": scenario, "additional_args": additional_args, "network": network}
        res = rpc_call("run", params)
        print(res)
    except Exception as e:
        print(f"Error running scenario: {e}")


@scenarios.command()
@click.option("--network", default="warnet", show_default=True)
def active(network: str = "warnet"):
    """
    List running scenarios on <--network> (default=warnet) as "name": "pid" pairs
    """
    try:
        result = rpc_call("list_running_scenarios", {"network": network})
        print(result)
    except Exception as e:
        print(f"Error listing scenarios: {e}")


@scenarios.command()
@click.argument("pid", type=int)
@click.option("--network", default="warnet", show_default=True)
def stop(pid: int, network: str = "warnet"):
    """
    Stop scenario with <pid> from running on <--network>
    """
    try:
        params = {"pid": pid, "network": network}
        res = rpc_call("stop_scenario", params)
        print(res)
    except Exception as e:
        print(f"Error stopping scenario: {e}")

