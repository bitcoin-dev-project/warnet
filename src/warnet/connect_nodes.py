import yaml
import logging
import networkx as nx
import docker
from warnet.generate_docker_compose import generate_docker_compose
import warnet.rpc_utils as bitcoin_cli

BITCOIN_GRAPH_FILE = './graphs/basic3.graphml'
CONFIG_FILE = 'config.yaml'

logging.basicConfig(level=logging.INFO)

def parse_config(config_file: str = CONFIG_FILE):
    """
    Parse the configuration file.

    :param config_file: The path to the configuration file
    :return: The parsed configuration
    """
    try:
        with open(config_file, "r") as file:
            return yaml.safe_load(file)
    except Exception as e:
        logging.error(f"An error occurred while reading the config file: {e}")

def delete_containers(client: docker.DockerClient, container_name_prefix: str = "warnet"):
    """
    Delete all containers with the specified name prefix.

    :param container_name_prefix: The prefix of the container names to filter.
    """
    try:
        containers = client.containers.list(all=True, filters={"name": container_name_prefix})
        for container in containers:
            container.remove(force=True)
        logging.info("  Removed all containers")
    except Exception as e:
        logging.error(f"An error occurred while deleting containers: {e}")

def generate_compose(graph_file: str):
    """
    Read a graph file and build a docker compose.

    :param graph_file: The path to the graph file
    """
    try:
        graph = nx.read_graphml(graph_file, node_type=int)
        version = [graph.nodes[node]["version"] for node in graph.nodes()]
        generate_docker_compose(node_count=len(graph.nodes()), version=version)
        logging.info(f"  Graph file contains {len(graph.nodes())} nodes and {len(graph.edges())} connections")
        logging.info("  Generated docker-compose.yml file")
    except Exception as e:
        logging.error(f"An error occurred while running new node: {e}")

def get_container_ip(client: docker.DockerClient, container_name: str):
    """
    Get the IP address of a container.

    :param container_name: The name of the container
    :return: The IP address of the container
    """
    try:
        container = client.containers.get(container_name)
        container.reload()
        cluster = container.attrs["NetworkSettings"]["Networks"].keys()
        cluster_name = list(cluster)[0]
        return container.attrs["NetworkSettings"]["Networks"][f"{cluster_name}"]["IPAddress"]
    except Exception as e:
        logging.error(f"An error occurred while getting container IP: {e}")

def get_containers(client: docker.DockerClient, container_name_prefix: str = "warnet"):
    """
    Get the names and instances of all containers with the specified name prefix.

    :param container_name_prefix: The prefix of the container names to filter.
    :return: A tuple containing the names and instances of the containers
    """
    containers = client.containers.list(all=True, filters={"name": container_name_prefix})
    container_names = [container.name for container in containers]
    return container_names, containers

def setup_network(client: docker.DockerClient, graph_file: str):
    """
    Setup and add nodes to the network.

    :param graph_file: The path to the graph file
    """
    try:
        graph = nx.read_graphml(graph_file, node_type=int)
        logging.info(get_containers(client))
        for edge in graph.edges():
            source = f"warnet_{str(edge[0])}"
            dest = f"warnet_{str(edge[1])}"
            source_container = client.containers.get(source)
            logging.info(f"Connecting node {source} to {dest}")
            bitcoin_cli.addnode(source_container, get_container_ip(client, dest))
    except Exception as e:
        logging.error(f"An error occurred while setting up the network: {e}")

def docker_compose():
    """
    Run docker compose
    """
    try:
        import subprocess
        subprocess.run(["docker-compose", "up", "-d"])
    except Exception as e:
        logging.error(f"An error occurred while running docker compose: {e}")

def main():
    client = docker.from_env()
    delete_containers(client)
    generate_compose(BITCOIN_GRAPH_FILE)
    docker_compose()
    setup_network(client, BITCOIN_GRAPH_FILE)

if __name__ == "__main__":
    main()
