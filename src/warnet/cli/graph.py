from io import BytesIO
from pathlib import Path

import click
import networkx as nx
from rich import print

from warnet.cli.rpc import rpc_call


@click.group(name="graph")
def graph():
    """Graph commands"""


def list_graph_generators() -> dict:
    modules = [
        nx.generators.classic,
        nx.generators.random_graphs,
        nx.generators.small,
        nx.generators.expanders,
        nx.generators.community,
        nx.generators.ego,
        nx.generators.geometric,
        nx.generators.lattice,
        nx.generators.line,
        nx.generators.mycielski,
        nx.generators.stochastic,
        nx.generators.triads,
    ]

    generators = {}
    for module in modules:
        for attr_name in dir(module):
            if not attr_name.startswith('_') and 'graph' in attr_name:
                generators[attr_name] = getattr(module, attr_name)

    return generators


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


@graph.command()
def list():
    """
    List many available graph generators available from networkx
    """
    print(list_graph_generators())


@graph.command()
@click.argument("graph_type", type=str)
@click.argument("num_nodes", default=10, type=int)
@click.option("--file", type=Path)
def create(graph_type: str, num_nodes: int, file: Path, **kwargs):
    """
    Create a graph of <graph_type> and <num_nodes> using networkx, optionally written to <--file>
    """
    generators = list_graph_generators()

    graph_func = generators.get(graph_type)
 
    if not graph_func:
        print(f"Graph type not found: {graph_type}")
        return
 
    try:
        graph = graph_func(num_nodes, **kwargs)
    except TypeError:
        print(f"Graph generator '{graph_type}' does not support 'num_nodes' parameter or other error occurred.")
        return

    # populate our fields
    for node in graph.nodes():
        graph.nodes[node]['version'] = "25.0"
        graph.nodes[node]['bitcoin_config'] = ""
        graph.nodes[node]['tc_netem'] = ""

    if file:
        file_path = Path(file)
        nx.write_graphml(graph, file_path)
        print(f"Generated graph and written to file: {file}")
        return

    bio = BytesIO()
    nx.write_graphml(graph, bio)
    xml_data = bio.getvalue()
    print(f"Generated graph:\n{xml_data.decode('utf-8')}")
