import logging
import docker
import networkx as nx

from .rpc_utils import addpeeraddress
from .docker_utils import get_container_ip, get_containers


logging.basicConfig(level=logging.INFO)


def connect_edges(client: docker.DockerClient, graph: nx.Graph):
    """
    Setup and add nodes to the network.

    :param graph: A NetworkX graph.
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
