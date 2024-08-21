import json
import logging
import random
from importlib.resources import files
from pathlib import Path

import networkx as nx
from jsonschema import validate

logger = logging.getLogger("utils")

SUPPORTED_TAGS = ["27.0", "26.0", "25.1", "24.2", "23.2", "22.2"]
DEFAULT_TAG = SUPPORTED_TAGS[0]
WEIGHTED_TAGS = [
    tag for index, tag in enumerate(reversed(SUPPORTED_TAGS)) for _ in range(index + 1)
]
SRC_DIR = files("warnet")


def create_cycle_graph(n: int, version: str, bitcoin_conf: str | None, random_version: bool):
    try:
        # Use nx.MultiDiGraph() so we get directed edges (source->target)
        # and still allow parallel edges (L1 p2p connections + LN channels)
        graph = nx.generators.cycle_graph(n, nx.MultiDiGraph())
    except TypeError as e:
        msg = f"Failed to create graph: {e}"
        logging.error(msg)
        return msg

    # Graph is a simply cycle graph with all nodes connected in a loop, including both ends.
    # Ensure each node has at least 8 outbound connections by making 7 more outbound connections
    for src_node in graph.nodes():
        logging.debug(f"Creating additional connections for node {src_node}")
        for _ in range(8):
            # Choose a random node to connect to
            # Make sure it's not the same node and they aren't already connected in either direction
            potential_nodes = [
                dst_node
                for dst_node in range(n)
                if dst_node != src_node
                and not graph.has_edge(dst_node, src_node)
                and not graph.has_edge(src_node, dst_node)
            ]
            if potential_nodes:
                chosen_node = random.choice(potential_nodes)
                graph.add_edge(src_node, chosen_node)
                logging.debug(f"Added edge: {src_node}:{chosen_node}")
        logging.debug(f"Node {src_node} edges: {graph.edges(src_node)}")

    # parse and process conf file
    conf_contents = ""
    if bitcoin_conf is not None:
        conf = Path(bitcoin_conf)
        if conf.is_file():
            with open(conf) as f:
                # parse INI style conf then dump using for_graph
                conf_dict = parse_bitcoin_conf(f.read())
                conf_contents = dump_bitcoin_conf(conf_dict, for_graph=True)

    # populate our custom fields
    for i, node in enumerate(graph.nodes()):
        if random_version:
            graph.nodes[node]["version"] = random.choice(WEIGHTED_TAGS)
        else:
            # One node demoing the image tag
            if i == 1:
                graph.nodes[node]["image"] = f"bitcoindevproject/bitcoin:{version}"
            else:
                graph.nodes[node]["version"] = version
        graph.nodes[node]["bitcoin_config"] = conf_contents
        graph.nodes[node]["tc_netem"] = ""
        graph.nodes[node]["build_args"] = ""
        graph.nodes[node]["exporter"] = False
        graph.nodes[node]["collect_logs"] = False

    convert_unsupported_attributes(graph)
    return graph


def convert_unsupported_attributes(graph: nx.Graph):
    # Sometimes networkx complains about invalid types when writing the graph
    # (it just generated itself!). Try to convert them here just in case.
    for _, node_data in graph.nodes(data=True):
        for key, value in node_data.items():
            if isinstance(value, set):
                node_data[key] = list(value)
            elif isinstance(value, int | float | str):
                continue
            else:
                node_data[key] = str(value)

    for _, _, edge_data in graph.edges(data=True):
        for key, value in edge_data.items():
            if isinstance(value, set):
                edge_data[key] = list(value)
            elif isinstance(value, int | float | str):
                continue
            else:
                edge_data[key] = str(value)


def load_schema():
    with open(SRC_DIR / "graph_schema.json") as schema_file:
        return json.load(schema_file)


def validate_graph_schema(graph: nx.Graph):
    """
    Validate a networkx.Graph against the node schema
    """
    graph_schema = load_schema()
    validate(instance=graph.graph, schema=graph_schema["graph"])
    for n in list(graph.nodes):
        validate(instance=graph.nodes[n], schema=graph_schema["node"])
    for e in list(graph.edges):
        validate(instance=graph.edges[e], schema=graph_schema["edge"])


def parse_bitcoin_conf(file_content):
    """
    Custom parser for INI-style bitcoin.conf

    Args:
    - file_content (str): The content of the INI-style file.

    Returns:
    - dict: A dictionary representation of the file content.
            Key-value pairs are stored as tuples so one key may have
            multiple values. Sections are represented as arrays of these tuples.
    """
    current_section = None
    result = {current_section: []}

    for line in file_content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("[") and line.endswith("]"):
            current_section = line[1:-1]
            result[current_section] = []
        elif "=" in line:
            key, value = line.split("=", 1)
            result[current_section].append((key.strip(), value.strip()))

    return result


def dump_bitcoin_conf(conf_dict, for_graph=False):
    """
    Converts a dictionary representation of bitcoin.conf content back to INI-style string.

    Args:
    - conf_dict (dict): A dictionary representation of the file content.

    Returns:
    - str: The INI-style string representation of the input dictionary.
    """
    result = []

    # Print global section at the top first
    values = conf_dict[None]
    for sub_key, sub_value in values:
        result.append(f"{sub_key}={sub_value}")

    # Then print any named subsections
    for section, values in conf_dict.items():
        if section is not None:
            result.append(f"\n[{section}]")
        else:
            continue
        for sub_key, sub_value in values:
            result.append(f"{sub_key}={sub_value}")

    if for_graph:
        return ",".join(result)

    # Terminate file with newline
    return "\n".join(result) + "\n"
