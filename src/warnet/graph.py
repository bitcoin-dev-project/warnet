from pathlib import Path

import click


@click.group(name="graph", hidden=True)
def graph():
    """Create and validate network graphs"""


@graph.command()
def import_json(infile: Path, outfile: Path, cb: str, ln_image: str):
    """
    Create a cycle graph with nodes imported from lnd `describegraph` JSON file,
    and additionally include 7 extra random outbounds per node. Include lightning
    channels and their policies as well.
    Returns XML file as string with or without --outfile option.
    """
    raise Exception("Not Implemented")
