import click

from .rpc import rpc_call


@click.group(name="bitcoin")
def bitcoin():
    """Control running bitcoin nodes"""


@bitcoin.command(context_settings={"ignore_unknown_options": True})
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


@bitcoin.command()
@click.argument("node", type=int, required=True)
@click.option("--network", default="warnet", show_default=True)
def debug_log(node, network):
    """
    Fetch the Bitcoin Core debug log from <node> in [network]
    """
    print(rpc_call("tank_debug_log", {"node": node, "network": network}))


@bitcoin.command()
@click.argument("node_a", type=int, required=True)
@click.argument("node_b", type=int, required=True)
@click.option("--network", default="warnet", show_default=True)
def messages(node_a, node_b, network):
    """
    Fetch messages sent between <node_a> and <node_b> in [network]
    """
    print(rpc_call("tank_messages", {"network": network, "node_a": node_a, "node_b": node_b}))


@bitcoin.command()
@click.argument("pattern", type=str, required=True)
@click.option("--network", default="warnet", show_default=True)
def grep_logs(pattern, network):
    """
    Grep combined logs via fluentd using regex <pattern>
    """
    print(rpc_call("logs_grep", {"network": network, "pattern": pattern}))
