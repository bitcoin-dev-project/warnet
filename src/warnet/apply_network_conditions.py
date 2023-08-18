import random
import logging
import re

import networkx as nx

from .net_demo_scenarios import network_scenarios
from .docker_utils import get_containers


def sanitize_tc_netem_command(command: str) -> bool:
    """
    Sanitize the tc-netem command to ensure it's valid and safe to execute, as we run it as root on a container.

    Args:
    - command (str): The tc-netem command to sanitize.

    Returns:
    - bool: True if the command is valid and safe, False otherwise.
    """
    if not command.startswith("tc qdisc add dev eth0 root netem"):
        return False

    tokens = command.split()[7:]  # Skip the prefix

    # Valid tc-netem parameters and their patterns
    valid_params = {
        "delay": r"^\d+ms(\s\d+ms)?(\sdistribution\s(normal|pareto|paretonormal|uniform))?$",
        "loss": r"^\d+(\.\d+)?%$",
        "duplicate": r"^\d+(\.\d+)?%$",
        "corrupt": r"^\d+(\.\d+)?%$",
        "reorder": r"^\d+(\.\d+)?%\s\d+(\.\d+)?%$",
        "rate": r"^\d+(kbit|mbit|gbit)$"
    }

    # Validate each param
    i = 0
    while i < len(tokens):
        param = tokens[i]
        if param not in valid_params:
            return False
        i += 1
        value_tokens = []
        while i < len(tokens) and tokens[i] not in valid_params:
            value_tokens.append(tokens[i])
            i += 1
        value = " ".join(value_tokens)
        if not re.match(valid_params[param], value):
            return False

    return True


def apply_network_conditions(client, graph):
    graph = nx.read_graphml(graph, node_type=int)

    for container_name, container in get_containers(client):
        parsed_node_id = int(container_name.split('_')[-1])

        # import pdb; pdb.set_trace()
        if parsed_node_id not in graph:
            logging.warning(f"No node with ID {parsed_node_id} found in the graph. Skipping container {container_name}.")
            continue

        node_data = graph.nodes[parsed_node_id]

        node_network_conditions = node_data.get("tc_netem", None)

        # If not, choose a random network condition for this node
        if not node_network_conditions:
            logging.debug(f"No network conditions found for node {container_name}, using random conditions")
            random_scenario_id = random.choice(list(network_scenarios.keys()))
            node_network_scenario = network_scenarios[random_scenario_id]
            node_network_conditions = node_network_scenario.command

        if not sanitize_tc_netem_command(node_network_conditions):
            logging.warning(f"Unsafe tc-netem conditions used: {node_network_conditions}, Skipping...")
            break

        # Apply the network condition to the container
        logging.info(f"Applying network conditions: {node_network_conditions} to node {container_name}")
        rcode, result = container.exec_run(node_network_conditions)
        if rcode == 0:
            logging.info(f"Successfully applied network conditions to {container_name}")
        else:
            logging.error(f"Error applying network conditions to {container_name}: {result}")
