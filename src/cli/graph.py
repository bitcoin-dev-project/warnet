from pathlib import Path

import click
from cli.rpc import rpc_call
from rich import print
from warnet.utils import DEFAULT_TAG


@click.group(name="graph")
def graph():
    """Graph commands"""


@graph.command()
@click.argument("number", type=int)
@click.option("--outfile", type=click.Path())
@click.option("--version", type=str, default=DEFAULT_TAG)
@click.option("--bitcoin_conf", type=click.Path())
@click.option("--random", is_flag=True)
def create(number: int, outfile: Path, version: str, bitcoin_conf: Path, random: bool = False):
    """
    Create a cycle graph with <n> nodes, and additionally include 7 extra random outbounds per node.
    Returns XML file as string with or without --outfile option
    """
    print(
        rpc_call(
            "graph_generate",
            {
                "n": number,
                "outfile": str(outfile) if outfile else "",
                "version": version,
                "bitcoin_conf": str(bitcoin_conf),
                "random": random,
            },
        )
    )


@graph.command()
@click.argument("graph", type=click.Path())
def validate(graph: Path):
    """
    Validate a <graph file> against the schema.
    """
    print(rpc_call("graph_validate", {"graph_path": Path(graph).as_posix()}))
