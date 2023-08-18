import logging
import docker
import networkx as nx

from .rpc_utils import addpeeraddress
from .docker_utils import get_container_ip, get_containers


logging.basicConfig(level=logging.INFO)

def create_graph_with_probability(num_nodes, p):
    graph = nx.erdos_renyi_graph(num_nodes, p, directed=True)
    for node in graph.nodes():
        graph.nodes[node]['version'] = '25.0'
    return graph


def generate_topology_with_probability(client, num_nodes, p):
    g = create_graph_with_probability(num_nodes, p)
    generate_topology(client, g)

def generate_topology(client: docker.DockerClient, g):
    """
    Creates a random network using an erdos-renyi model.

    :param client: docker client
    :param num_nodes: number of nodes
    :param p: probability of a connection to be created
    :return:
    """

    logging.info("Creating scenario with a random topology: {} nodes and {} edges".format(len(g.nodes()), g.number_of_edges()))
    connect_edges(client, g)

def read_graph_from_file(graph_file: str):
    try:
        return nx.read_graphml(graph_file, node_type=int)
    except Exception as e:
        logging.error(f"An error occurred while reading {graph_file}: {e}")

def connect_edges(client: docker.DockerClient, graph):
    """
    Setup and add nodes to the network.

    :param graph_file: The path to the graph file
    """
    try:
        logging.info(get_containers(client))
        for edge in graph.edges():
            source = f"warnet_{str(edge[0])}"
            dest = f"warnet_{str(edge[1])}"
            source_container = client.containers.get(source)
            logging.info(f"Connecting node {source} to {dest}")
            addpeeraddress(source_container, get_container_ip(client, dest))
    except Exception as e:
        logging.error(f"An error occurred while setting up the network: {e}")

def generate_topology_from_file(client: docker.DockerClient, graph_file: str):
    graph = read_graph_from_file(graph_file)
    generate_topology(client, graph)

