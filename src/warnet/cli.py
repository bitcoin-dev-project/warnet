import requests
from typing import Optional, Any, Tuple, Dict, Union
from pathlib import Path

from jsonrpcclient import Ok, parse, request
import click
from rich import print

from templates import TEMPLATES
from warnet import warnet
from warnet.warnetd import WARNETD_PORT

EXAMPLE_GRAPH_FILE = TEMPLATES / "example.graphml"


def rpc_call(rpc_method, params: Optional[Union[Dict[str, Any], Tuple[Any, ...]]]):
    payload = request(rpc_method, params)
    response = requests.post(f"http://localhost:{WARNETD_PORT}/api", json=payload)
    parsed = parse(response.json())

    if isinstance(parsed, Ok):
        return parsed.result
    else:
        print(parsed)
        raise Exception(parsed.message)


@click.group()
def cli():
    pass

@click.group(name="debug")
def debug():
    """Debug commands"""
cli.add_command(debug)

@click.group(name="scenarios")
def scenarios():
    """Scenario commands"""
cli.add_command(scenarios)

@click.group(name="network")
def network():
    """Network commands"""
cli.add_command(network)


@cli.command(name="help")
@click.argument("command", required=False, default=None)
@click.pass_context
def help_command(ctx, command):
    """
    Display help information for the given command.
    If no command is given, display help for the main CLI.
    """
    if command is None:
        # Display help for the main CLI
        print(ctx.parent.get_help())
        return

    # Fetch the command object
    cmd_obj = cli.get_command(ctx, command)

    if cmd_obj is None:
        print(f"Unknown command: {command}")
        return

    # Extract only the relevant help information (excluding the initial usage line)
    help_info = cmd_obj.get_help(ctx).split("\n", 1)[-1].strip()

    # Extract the arguments of the command
    arguments = [param.human_readable_name.upper() for param in cmd_obj.params if isinstance(param, click.Argument)]

    # Determine the correct usage string based on whether the command has subcommands
    if isinstance(cmd_obj, click.Group) and cmd_obj.list_commands(ctx):
        usage_str = f"Usage: warnet {command} [OPTIONS] COMMAND [ARGS...]\n\n{help_info}"
    else:
        args_str = " ".join(arguments)
        usage_str = f"Usage: warnet {command} [OPTIONS] {args_str}\n\n{help_info}"
 
    print(usage_str)

cli.add_command(help_command)


@cli.command(context_settings={"ignore_unknown_options": True})
@click.argument('node', type=int)
@click.argument('method', type=str, nargs=-1)  # this will capture all remaining arguments
@click.option('--params', type=str, multiple=True, default=())
@click.option('--network', default='warnet', show_default=True)
def rpc(node, method, params, network):
    """
    Call bitcoin-cli <method> <params> on <node> in <--network>
    """
    if len(method) > 2:
        raise click.BadArgumentUsage("You can provide at most two arguments for 'method'.")

    # Convert tuple to space-separated string
    method_str = " ".join(method)

    try:
        result = rpc_call(
            "bcli",
            {"network": network, "node": node, "method": method_str, "params": params},
        )
        print(result)
    except Exception as e:
        print(f"bitcoin-cli {method_str} {params} failed on node {node}:\n{e}")


@cli.command()
@click.argument('node', type=int, required=True)
@click.option('--network', default='warnet', show_default=True)
def debug_log(node, network):
    """
    Fetch the Bitcoin Core debug log from <node> in [network]
    """
    try:
        result = rpc_call("debug_log", {"node": node, "network": network})
        print(result)
    except Exception as e:
        print(f"In our pursuit of knowledge from node {node}, we were thwarted: {e}")


@cli.command()
@click.argument('node_a', type=int, required=True)
@click.argument('node_b', type=int, required=True)
@click.option('--network', default='warnet', show_default=True)
def messages(node_a, node_b, network):
    """
    Fetch messages sent between <node_a> and <node_b> in <network>
    """
    import logging
    logging.warning(f"got args: {node_a}, {node_b}, {network}")
    try:
        result = rpc_call(
            "messages", {"network": network, "node_a": node_a, "node_b": node_b}
        )
        print(result)
    except Exception as e:
        print(
            f"Amidst the fog of war, we failed to relay messages between strongholds {node_a} and {node_b}: {e}"
        )


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


@scenarios.command()
@click.argument('scenario', type=str)
def run(scenario):
    """
    Run <scenario> from the Warnet Test Framework
    """
    try:
        res = rpc_call("run", {"scenario": scenario})
        print(res)
    except Exception as e:
        print(f"Error running scenario: {e}")


@debug.command()
@click.argument('graph_file', type=str)
@click.option('--network', default='warnet', show_default=True)
def generate_compose(graph_file: str, network: str = "warnet"):
    """
    Generate the docker-compose file for a given <graph_file> and <--network> name and return it.
    """
    try:
        result = rpc_call("generate_compose", {"graph_file": graph_file, "network": network})
        print(result)
    except Exception as e:
        print(f"Error generating compose: {e}")

@network.command()
@click.argument('graph_file', default=EXAMPLE_GRAPH_FILE, type=click.Path())
@click.option('--force', default=False, is_flag=True, type=bool)
@click.option('--network', default='warnet', show_default=True)
def start(graph_file: Path = EXAMPLE_GRAPH_FILE, force: bool = False, network: str = "warnet"):
    """
    Start a warnet with topology loaded from a <graph_file> into <--network> (default: "warnet")
    """
    try:
        result = rpc_call("from_file", {"graph_file": str(graph_file), "force": force, "network": network})
        print(result)
    except Exception as e:
        print(f"Error creating network: {e}")


@network.command()
@click.option('--network', default='warnet', show_default=True)
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
@click.option('--network', default='warnet', show_default=True)
def down(network: str = "warnet"):
    """
    Run 'docker-compose down on a warnet named <--network> (default: "warnet").
    """
    try:
        result = rpc_call("down", {"network": network})
        print(result)
    except Exception as e:
        print(f"As we endeavored to cease operations, adversity struck: {e}")


@cli.command()
def stop():
    """
    Stop the warnetd daemon.
    """
    try:
        result = rpc_call("stop", None)
        print(result)
    except Exception as e:
        print(f"As we endeavored to cease operations, adversity struck: {e}")


if __name__ == "__main__":
    cli()
