import click
from rich import print as richprint

from templates import TEMPLATES
from warnet.cli.debug import debug
from warnet.cli.graph import graph
from warnet.cli.network import network
from warnet.cli.rpc import rpc_call
from warnet.cli.scenarios import scenarios

EXAMPLE_GRAPH_FILE = TEMPLATES / "example.graphml"


@click.group()
def cli():
    pass


cli.add_command(debug)
cli.add_command(graph)
cli.add_command(scenarios)
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
        richprint(ctx.parent.get_help())
        return

    # Fetch the command object
    cmd_obj = cli.get_command(ctx, command)

    if cmd_obj is None:
        richprint(f"Unknown command: {command}")
        return

    # Extract only the relevant help information (excluding the initial usage line)
    # help_info = cmd_obj.get_help(ctx).split("\n", 1)[-1].strip()
    help_info = cmd_obj.get_help(ctx).strip()


    # Extract the arguments of the command
    arguments = [
        param.human_readable_name.upper()
        for param in cmd_obj.params
        if isinstance(param, click.Argument)
    ]

    # Determine the correct usage string based on whether the command has subcommands
    if isinstance(cmd_obj, click.Group) and cmd_obj.list_commands(ctx):
        usage_str = (
            f"Usage: warnet {command} [OPTIONS] COMMAND [ARGS...]\n\n{help_info}"
        )
    else:
        args_str = " ".join(arguments)
        usage_str = f"Usage: warnet {command} [OPTIONS] {args_str}\n\n{help_info}"

    richprint(usage_str)


cli.add_command(help_command)


@cli.command(context_settings={"ignore_unknown_options": True})
@click.argument("node", type=int)
@click.argument(
    "method", type=str, nargs=-1
)  # this will capture all remaining arguments
@click.option("--params", type=str, multiple=True, default=())
@click.option("--network", default="warnet", show_default=True)
def rpc(node, method, params, network):
    """
    Call bitcoin-cli <method> <params> on <node> in <--network>
    """
    if len(method) > 2:
        raise click.BadArgumentUsage(
            "You can provide at most two arguments for 'method'."
        )

    # Convert tuple to space-separated string
    method_str = " ".join(method)

    try:
        result = rpc_call(
            "bcli",
            {"network": network, "node": node, "method": method_str, "params": params},
        )
        richprint(result)
    except Exception as e:
        richprint(f"bitcoin-cli {method_str} {params} failed on node {node}:\n{e}")


@cli.command()
@click.argument("node", type=int, required=True)
@click.option("--network", default="warnet", show_default=True)
def debug_log(node, network):
    """
    Fetch the Bitcoin Core debug log from <node> in [network]
    """
    try:
        result = rpc_call("debug_log", {"node": node, "network": network})
        print(result)
    except Exception as e:
        richprint(f"In our pursuit of knowledge from node {node}, we were thwarted: {e}")


@cli.command()
@click.argument("node_a", type=int, required=True)
@click.argument("node_b", type=int, required=True)
@click.option("--network", default="warnet", show_default=True)
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
        richprint(result)
    except Exception as e:
        richprint(
            f"Error fetching messages between {node_a} and {node_b}: {e}"
        )


@cli.command()
def stop():
    """
    Stop warnetd.
    """
    try:
        result = rpc_call("stop", None)
        richprint(result)
    except Exception as e:
        richprint(f"Error stopping warnetd: {e}")


if __name__ == "__main__":
    cli()
