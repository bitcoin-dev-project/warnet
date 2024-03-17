import click
from cli.debug import debug
from cli.graph import graph
from cli.image import image
from cli.network import network
from cli.rpc import rpc_call
from cli.scenarios import scenarios
from requests.exceptions import ConnectionError
from rich import print as richprint


@click.group()
def cli():
    pass


cli.add_command(debug)
cli.add_command(graph)
cli.add_command(image)
cli.add_command(network)
cli.add_command(scenarios)


@cli.command(name="help")
@click.argument("commands", required=False, nargs=-1)
@click.pass_context
def help_command(ctx, commands):
    """
    Display help information for the given [command] (and sub-command).
    If no command is given, display help for the main CLI.
    """
    if not commands:
        # Display help for the main CLI
        richprint(ctx.parent.get_help())
        return

    # Recurse down the subcommands, fetching the command object for each
    cmd_obj = cli
    for command in commands:
        cmd_obj = cmd_obj.get_command(ctx, command)
        if cmd_obj is None:
            richprint(f'Unknown command "{command}" in {commands}')
            return
        ctx = click.Context(cmd_obj, info_name=command, parent=ctx)

    if cmd_obj is None:
        richprint(f"Unknown command: {commands}")
        return

    # Get the help info
    help_info = cmd_obj.get_help(ctx).strip()
    # Get rid of the duplication
    help_info = help_info.replace("Usage: warcli help [COMMANDS]...", "Usage: warcli", 1)
    richprint(help_info)


cli.add_command(help_command)


@cli.command(context_settings={"ignore_unknown_options": True})
@click.argument("node", type=int)
@click.argument("method", type=str)
@click.argument("params", type=str, nargs=-1)  # this will capture all remaining arguments
@click.option("--network", default="warnet", show_default=True)
def rpc(node, method, params, network):
    """
    Call bitcoin-cli <method> [params] on <node> in [network]
    """
    print(
        rpc_call(
            "tank_bcli", {"network": network, "node": node, "method": method, "params": params}
        )
    )


@cli.command(context_settings={"ignore_unknown_options": True})
@click.argument("node", type=int)
@click.argument("command", type=str, required=True, nargs=-1)
@click.option("--network", default="warnet", show_default=True, type=str)
def lncli(node: int, command: tuple, network: str):
    """
    Call lightning cli <command> on <node> in [network]
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
    Fetch messages sent between <node_a> and <node_b> in [network]
    """
    print(rpc_call("tank_messages", {"network": network, "node_a": node_a, "node_b": node_b}))


@cli.command()
@click.argument("pattern", type=str, required=True)
@click.option("--network", default="warnet", show_default=True)
def grep_logs(pattern, network):
    """
    Grep combined logs via fluentd using regex <pattern>
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
