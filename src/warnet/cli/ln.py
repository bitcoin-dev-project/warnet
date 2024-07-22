import click

from .rpc import rpc_call


@click.group(name="ln")
def ln():
    """Control running lightning nodes"""


@ln.command(context_settings={"ignore_unknown_options": True})
@click.argument("node", type=int)
@click.argument("command", type=str, required=True, nargs=-1)
@click.option("--network", default="warnet", show_default=True, type=str)
def rpc(node: int, command: tuple, network: str):
    """
    Call lightning cli rpc <command> on <node> in [network]
    """
    print(
        rpc_call(
            "tank_lncli",
            {"network": network, "node": node, "command": command},
        )
    )


@ln.command(context_settings={"ignore_unknown_options": True})
@click.argument("node", type=int)
@click.option("--network", default="warnet", show_default=True, type=str)
def pubkey(node: int, network: str):
    """
    Get lightning node pub key on <node> in [network]
    """
    print(
        rpc_call(
            "tank_ln_pub_key",
            {"network": network, "node": node},
        )
    )
