from pathlib import Path

import click
from rich import print

from warnet.cli.rpc import rpc_call


@click.group(name="graph")
def graph():
    """Graph commands"""


@graph.command()
@click.argument("num_nodes", default=20, type=int)
@click.argument("probability", default=0.3, type=float)
@click.option("--file", type=Path)
@click.option("--random", default=False, type=bool)
def random(num_nodes: int, probability: float, file: Path, random: bool = False):
    """
    Creates a random network using an erdos-renyi model, with <num_nodes> of
    different versions each connected together with a probability of
    <probability>, optionally saving to <--file>.
    """
    try:
        result = rpc_call(
            "graph_generate",
            {"num_nodes": num_nodes, "probability": probability, "file": str(file) if file else "", "random": random},
        )
        print(result)
    except Exception as e:
        print(f"Error generating graph: {e}")


