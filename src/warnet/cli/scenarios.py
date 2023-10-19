import click
from rich import print

from warnet.cli.rpc import rpc_call

@click.group(name="scenarios")
def scenarios():
    """Scenario commands"""


@scenarios.command()
def list():
    """
    List available scenarios in the Warnet Test Framework
    """
    try:
        result = rpc_call("scenarios_list", None)
        for sc_name, sc_help in result:
            print(f"{sc_name.ljust(20)}{sc_help}")
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
        res = rpc_call("scenarios_run", params)
        print(res)
    except Exception as e:
        print(f"Error running scenario: {e}")


@scenarios.command()
def active():
    """
    List running scenarios "name": "pid" pairs
    """
    try:
        result = rpc_call("scenarios_list_running", {})

        template = "\t%-8.8s%-65.64s%-10.10s%-10.9s\n"
        sc_str = template % ("PID", "Command", "Network", "Active")
        for sc in result:
            sc_str += template % (sc["pid"], sc["cmd"], sc["network"], sc["active"])
        print(sc_str)
    except Exception as e:
        print(f"Error listing scenarios: {e}")


@scenarios.command()
@click.argument("pid", type=int)
def stop(pid: int):
    """
    Stop scenario with PID <pid> from running
    """
    try:
        params = {"pid": pid}
        res = rpc_call("scenarios_stop", params)
        print(res)
    except Exception as e:
        print(f"Error stopping scenario: {e}")

