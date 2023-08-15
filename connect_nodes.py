import yaml
import logging
import networkx as nx
import docker
from generate_docker_compose import generate_docker_compose
import rpc_utils as bitcoin_cli

BITCOIN_GRAPH_FILE = './graphs/basic3.graphml'


def parse_config():
    with open("config.yaml", "r") as file:
        return yaml.safe_load(file)

def delete_containers():
    """
    Delete all containers with the name "warnet"
    """
    client = docker.from_env()
    containers = client.containers.list(all=True, filters={"name": "warnet"})
    for container in containers:
        container.remove(force=True)
    logging.info("  Removed all containers")


def run_new_node(graph_file):
    """
    Run a new Bitcoin node
    If there is an existing node, it will be removed
    :param graph_file: The path to the graph file
    """
    delete_containers()
    graph = nx.read_graphml(graph_file, node_type=int)
    version = [graph.nodes[node]["version"] for node in graph.nodes()]
    generate_docker_compose(node_count=len(graph.nodes()),
                            version=version)
    logging.info("  Graph file contains {} nodes and {} connections".format(
        len(graph.nodes()), len(graph.edges())))
    logging.info("  Generated docker-compose.yml file")


def get_container_ip(container_name):
    """
    Get the IP address of a container
    :param container_name: The name of the container
    :return: The IP address of the container
    """
    client = docker.from_env()
    container = client.containers.get(container_name)
    container.reload()
    cluster = container.attrs["NetworkSettings"]["Networks"].keys()
    cluster_name = list(cluster)[0]

    return container.attrs["NetworkSettings"]["Networks"][f"{cluster_name}"]["IPAddress"]

def get_containers():
    client = docker.from_env()
    containers = client.containers.list(all=True, filters={"name": "warnet"})
    container_names = []
    for container in containers:
        container_names.append(container.name)
    return container_names, containers
   
    

def add_nodes_to_network(graph_file):
    """
    Add nodes to the network
    :param graph_file: The path to the graph file
    """
    graph = nx.read_graphml(graph_file, node_type=int)
    print(get_containers())
    for edge in graph.edges():
        source = f"warnet_{str(edge[0])}"
        dest = f"warnet_{str(edge[1])}"
        client = docker.from_env()
        source_container = client.containers.get(source)
        logging.info("  Connecting to container")

        bitcoin_cli.addnode(source_container, get_container_ip(dest))


def start_nodes():
    """
    Start all nodes in the network
    """
    import subprocess
    subprocess.run(["docker-compose", "up", "-d"])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_new_node(BITCOIN_GRAPH_FILE)
    start_nodes()
    add_nodes_to_network(BITCOIN_GRAPH_FILE)
