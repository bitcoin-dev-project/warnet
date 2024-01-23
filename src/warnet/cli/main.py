import click
from requests.exceptions import ConnectionError
from rich import print as richprint
from warnet.cli.debug import debug
from warnet.cli.image import image
from warnet.cli.graph import graph
from warnet.cli.network import network
from warnet.cli.rpc import rpc_call
from warnet.cli.scenarios import scenarios


@click.group()
def cli():
    pass


cli.add_command(debug)
cli.add_command(graph)
cli.add_command(image)
cli.add_command(network)
cli.add_command(scenarios)


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
        usage_str = f"Usage: warnet {command} [OPTIONS] COMMAND [ARGS...]\n\n{help_info}"
    else:
        args_str = " ".join(arguments)
        usage_str = f"Usage: warnet {command} [OPTIONS] {args_str}\n\n{help_info}"

    richprint(usage_str)


cli.add_command(help_command)


@cli.command(context_settings={"ignore_unknown_options": True})
@click.argument("node", type=int)
@click.argument("method", type=str, nargs=-1)  # this will capture all remaining arguments
@click.option("--params", type=str, multiple=True, default=())
@click.option("--network", default="warnet", show_default=True)
def rpc(node, method, params, network):
    """
    Call bitcoin-cli <method> <params> on <node> in <--network>
    """
    if len(method) > 2:
        raise click.BadArgumentUsage("You can provide at most two arguments for 'method'.")

    # Convert tuple to space-separated string
    method_str = " ".join(method)

    print(
        rpc_call(
            "tank_bcli",
            {"network": network, "node": node, "method": method_str, "params": params},
        )
    )


@cli.command(context_settings={"ignore_unknown_options": True})
@click.argument("node", type=int)
@click.argument("command", type=str, required=True, nargs=-1)
@click.option("--network", default="warnet", show_default=True, type=str)
def lncli(node: int, command: tuple, network: str):
    """
    Call lightning cli <command> on <node> in <--network>
    """
    print(
        rpc_call(
            "tank_lncli",
            {"network": network, "node": node, "command": command},
        )
    )


@cli.command()
@click.argument("node", type=int, required=True)
@click.option("--network", default="warnet", show_default=True)
def debug_log(node, network):
    """
    Fetch the Bitcoin Core debug log from <node> in [network]
    """
    print(rpc_call("tank_debug_log", {"node": node, "network": network}))


@cli.command()
@click.argument("node_a", type=int, required=True)
@click.argument("node_b", type=int, required=True)
@click.option("--network", default="warnet", show_default=True)
def messages(node_a, node_b, network):
    """
    Fetch messages sent between <node_a> and <node_b> in <network>
    """
    print(rpc_call("tank_messages", {"network": network, "node_a": node_a, "node_b": node_b}))


@cli.command()
@click.argument("pattern", type=str, required=True)
@click.option("--network", default="warnet", show_default=True)
def grep_logs(pattern, network):
    """
    Grep combined logs via fluentd using regex [pattern]
    """
    print(rpc_call("logs_grep", {"network": network, "pattern": pattern}))


@cli.command()
def stop():
    """
    Stop warnet.
    """
    try:
        rpc_call("server_stop", None)
    except ConnectionError:
        # This is a successful stop in this context, as they disconnected us
        richprint("Stopped warnet")
    except Exception as e:
        print(e)


if __name__ == "__main__":
    cli()
