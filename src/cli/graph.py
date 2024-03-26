from io import BytesIO
from pathlib import Path

import click
import networkx as nx
from rich import print
from warnet.utils import DEFAULT_TAG, create_cycle_graph, validate_graph_schema


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
    Create a cycle graph with <number> nodes, and include 7 extra random outbounds per node.
    Returns XML file as string with or without --outfile option
    """
    graph = create_cycle_graph(number, version, bitcoin_conf, random)

    if outfile:
        file_path = Path(outfile)
        nx.write_graphml(graph, file_path, named_key_ids=True)
        return f"Generated graph written to file: {outfile}"
    bio = BytesIO()
    nx.write_graphml(graph, bio, named_key_ids=True)
    xml_data = bio.getvalue()
    print(xml_data.decode("utf-8"))


@graph.command()
@click.argument("graph", type=click.Path())
def validate(graph: Path):
    """
    Validate a <graph file> against the schema.
    """
    with open(graph) as f:
        graph = nx.parse_graphml(f.read(), node_type=int)
    return validate_graph_schema(graph)
