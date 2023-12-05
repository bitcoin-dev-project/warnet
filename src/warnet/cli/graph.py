from pathlib import Path
from typing import List

import click
from rich import print

from warnet.cli.rpc import rpc_call
from warnet.utils import DEFAULT_TAG


@click.group(name="graph")
def graph():
    """Graph commands"""


@graph.command()
@click.argument("params", nargs=-1, type=str)
@click.option("--outfile", type=Path)
@click.option("--version", type=str, default=DEFAULT_TAG)
@click.option("--bitcoin_conf", type=Path)
@click.option("--random", is_flag=True)
def create(
    params: List[str], outfile: Path, version: str, bitcoin_conf: Path, random: bool = False
):
    """
    Create a graph file of type random AS graph with [params]
    """
    try:
        result = rpc_call(
            "graph_generate",
            {
                "params": params,
                "outfile": str(outfile) if outfile else "",
                "version": version,
                "bitcoin_conf": str(bitcoin_conf),
                "random": random,
            },
        )
        print(result)
    except Exception as e:
        print(f"Error generating graph: {e}")
