from pathlib import Path

import click

from .util import DEFAULT_TAG


@click.group(name="graph")
def graph():
    """Create and validate network graphs"""


@graph.command()
@click.argument("number", type=int)
@click.option("--outfile", type=click.Path())
@click.option("--version", type=str, default=DEFAULT_TAG)
@click.option("--bitcoin_conf", type=click.Path())
@click.option("--random", is_flag=True)
def create(number: int, outfile: Path, version: str, bitcoin_conf: Path, random: bool = False):
    """
    Create a cycle graph with <number> nodes, and include 7 extra random outbounds per node.
    Returns XML file as string with or without --outfile option
    """
    raise Exception("Not Implemented")


@graph.command()
@click.argument("infile", type=click.Path())
@click.option("--outfile", type=click.Path())
@click.option("--cb", type=str)
@click.option("--ln_image", type=str)
def import_json(infile: Path, outfile: Path, cb: str, ln_image: str):
    """
    Create a cycle graph with nodes imported from lnd `describegraph` JSON file,
    and additionally include 7 extra random outbounds per node. Include lightning
    channels and their policies as well.
    Returns XML file as string with or without --outfile option.
    """
    raise Exception("Not Implemented")
