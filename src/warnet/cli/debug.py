import click
from rich import print

from warnet.cli.rpc import rpc_call

@click.group(name="debug")
def debug():
    """Debug commands"""


@debug.command()
@click.argument("graph_file", type=str)
@click.option("--network", default="warnet", show_default=True)
def generate_deployment(graph_file: str, network: str):
    """
    Generate the deployment file for a given <graph_file> and <--network> (default: "warnet") name and return it.
    """
    try:
        result = rpc_call(
            "generate_deployment", {"graph_file": graph_file, "network": network}
        )
        print(result)
    except Exception as e:
        print(f"Error generating compose: {e}")

