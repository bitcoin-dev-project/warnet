import click
from cli.rpc import rpc_call
from rich import print


@click.group(name="debug")
def debug():
    """Debug commands"""


@debug.command()
@click.argument("graph_file", type=str)
@click.option("--network", default="warnet", show_default=True)
def generate_compose(graph_file: str, network: str):
    """
    Generate the docker-compose file for a given <graph_file> and [network] and return it.
    """
    print(rpc_call("generate_compose", {"graph_file": graph_file, "network": network}))
