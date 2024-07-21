import functools
import ipaddress
import json
import logging
import os
import random
import re
import stat
import subprocess
import sys
import time
from io import BytesIO
from pathlib import Path

import networkx as nx
from jsonschema import validate
from test_framework.messages import ser_uint256
from test_framework.p2p import MESSAGEMAP

from .schema import SCHEMA

logger = logging.getLogger("utils")


SUPPORTED_TAGS = ["27.0", "26.0", "25.1", "24.2", "23.2", "22.2"]
DEFAULT_TAG = SUPPORTED_TAGS[0]
WEIGHTED_TAGS = [
    tag for index, tag in enumerate(reversed(SUPPORTED_TAGS)) for _ in range(index + 1)
]
GRAPH_SCHEMA_PATH = SCHEMA / "graph_schema.json"


class NonErrorFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool | logging.LogRecord:
        return record.levelno <= logging.INFO


def exponential_backoff(max_retries=5, base_delay=1, max_delay=32):
    """
    A decorator for exponential backoff.

    Parameters:
    - max_retries: Maximum number of retries before giving up.
    - base_delay: Initial delay in seconds.
    - max_delay: Maximum delay in seconds.
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    error_msg = str(e).replace("\n", " ").replace("\t", " ")
                    logger.error(f"rpc error: {error_msg}")
                    retries += 1
                    if retries == max_retries:
                        raise e
                    delay = min(base_delay * (2**retries), max_delay)
                    logger.warning(f"exponential_backoff: retry in {delay} seconds...")
                    time.sleep(delay)

        return wrapper

    return decorator


def handle_json(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        result = ""
        try:
            result = func(*args, **kwargs)
            logger.debug(f"{result=:}")
            if isinstance(result, dict):
                return result
            parsed_result = json.loads(result)
            return parsed_result
        except json.JSONDecodeError as e:
            logging.error(
                f"JSON parsing error in {func.__name__}: {e}. Undecodable result: {result}"
            )
            raise
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}")
            raise

    return wrapper


def get_architecture():
    """
    Get the architecture of the machine.
    :return: The architecture of the machine or None if an error occurred
    """
    result = subprocess.run(["uname", "-m"], stdout=subprocess.PIPE)
    arch = result.stdout.decode("utf-8").strip()
    if arch == "x86_64":
        arch = "amd64"
    if arch is None:
        raise Exception("Failed to detect architecture.")
    return arch


def generate_ipv4_addr(subnet):
    """
    Generate a valid random IPv4 address within the given subnet.

    :param subnet: Subnet in CIDR notation (e.g., '100.0.0.0/8')
    :return: Random IP address within the subnet
    """
    reserved_ips = [
        "0.0.0.0/8",
        "10.0.0.0/8",
        "100.64.0.0/10",
        "127.0.0.0/8",
        "169.254.0.0/16",
        "172.16.0.0/12",
        "192.0.0.0/24",
        "192.0.2.0/24",
        "192.88.99.0/24",
        "192.168.0.0/16",
        "198.18.0.0/15",
        "198.51.100.0/24",
        "203.0.113.0/24",
        "224.0.0.0/4",
    ]

    def is_public(ip):
        for reserved in reserved_ips:
            if ipaddress.ip_address(ip) in ipaddress.ip_network(reserved, strict=False):
                return False
        return True

    network = ipaddress.ip_network(subnet, strict=False)

    # Generate a random IP within the subnet range
    while True:
        ip_int = random.randint(int(network.network_address), int(network.broadcast_address))
        ip_str = str(ipaddress.ip_address(ip_int))
        if is_public(ip_str):
            return ip_str


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
        "rate": r"^\d+(kbit|mbit|gbit)$",
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


def to_jsonable(obj):
    HASH_INTS = [
        "blockhash",
        "block_hash",
        "hash",
        "hashMerkleRoot",
        "hashPrevBlock",
        "hashstop",
        "prev_header",
        "sha256",
        "stop_hash",
    ]

    HASH_INT_VECTORS = [
        "hashes",
        "headers",
        "vHave",
        "vHash",
    ]

    if hasattr(obj, "__dict__"):
        return obj.__dict__
    elif hasattr(obj, "__slots__"):
        ret = {}  # type: Any
        for slot in obj.__slots__:
            val = getattr(obj, slot, None)
            if slot in HASH_INTS and isinstance(val, int):
                ret[slot] = ser_uint256(val).hex()
            elif slot in HASH_INT_VECTORS and all(isinstance(a, int) for a in val):
                ret[slot] = [ser_uint256(a).hex() for a in val]
            else:
                ret[slot] = to_jsonable(val)
        return ret
    elif isinstance(obj, list):
        return [to_jsonable(a) for a in obj]
    elif isinstance(obj, bytes):
        return obj.hex()
    else:
        return obj


# This function is a hacked-up copy of process_file() from
# Bitcoin Core contrib/message-capture/message-capture-parser.py
def parse_raw_messages(blob, outbound):
    TIME_SIZE = 8
    LENGTH_SIZE = 4
    MSGTYPE_SIZE = 12

    messages = []
    offset = 0
    while True:
        # Read the Header
        header_len = TIME_SIZE + LENGTH_SIZE + MSGTYPE_SIZE
        tmp_header_raw = blob[offset : offset + header_len]

        offset = offset + header_len
        if not tmp_header_raw:
            break
        tmp_header = BytesIO(tmp_header_raw)
        time = int.from_bytes(tmp_header.read(TIME_SIZE), "little")  # type: int
        msgtype = tmp_header.read(MSGTYPE_SIZE).split(b"\x00", 1)[0]  # type: bytes
        length = int.from_bytes(tmp_header.read(LENGTH_SIZE), "little")  # type: int

        # Start converting the message to a dictionary
        msg_dict = {}
        msg_dict["outbound"] = outbound
        msg_dict["time"] = time
        msg_dict["size"] = length  # "size" is less readable here, but more readable in the output

        msg_ser = BytesIO(blob[offset : offset + length])
        offset = offset + length

        # Determine message type
        if msgtype not in MESSAGEMAP:
            # Unrecognized message type
            try:
                msgtype_tmp = msgtype.decode()
                if not msgtype_tmp.isprintable():
                    raise UnicodeDecodeError
                msg_dict["msgtype"] = msgtype_tmp
            except UnicodeDecodeError:
                msg_dict["msgtype"] = "UNREADABLE"
            msg_dict["body"] = msg_ser.read().hex()
            msg_dict["error"] = "Unrecognized message type."
            messages.append(msg_dict)
            print(f"WARNING - Unrecognized message type {msgtype}", file=sys.stderr)
            continue

        # Deserialize the message
        msg = MESSAGEMAP[msgtype]()
        msg_dict["msgtype"] = msgtype.decode()

        try:
            msg.deserialize(msg_ser)
        except KeyboardInterrupt:
            raise
        except Exception:
            # Unable to deserialize message body
            msg_ser.seek(0, os.SEEK_SET)
            msg_dict["body"] = msg_ser.read().hex()
            msg_dict["error"] = "Unable to deserialize message."
            messages.append(msg_dict)
            print("WARNING - Unable to deserialize message", file=sys.stderr)
            continue

        # Convert body of message into a jsonable object
        if length:
            msg_dict["body"] = to_jsonable(msg)
        messages.append(msg_dict)
    return messages


def gen_config_dir(network: str) -> Path:
    """
    Determine a config dir based on network name
    """
    config_dir = os.getenv("XDG_CONFIG_HOME", os.path.expanduser("~/.warnet"))
    config_dir = Path(config_dir) / "warnet" / network
    return config_dir


def remove_version_prefix(version_str):
    if version_str.startswith("0."):
        return version_str[2:]
    return version_str


def set_execute_permission(file_path):
    current_permissions = os.stat(file_path).st_mode
    os.chmod(file_path, current_permissions | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def create_cycle_graph(n: int, version: str, bitcoin_conf: str | None, random_version: bool):
    try:
        # Use nx.MultiDiGraph() so we get directed edges (source->target)
        # and still allow parallel edges (L1 p2p connections + LN channels)
        graph = nx.generators.cycle_graph(n, nx.MultiDiGraph())
    except TypeError as e:
        msg = f"Failed to create graph: {e}"
        logger.error(msg)
        return msg

    # Graph is a simply cycle graph with all nodes connected in a loop, including both ends.
    # Ensure each node has at least 8 outbound connections by making 7 more outbound connections
    for src_node in graph.nodes():
        logger.debug(f"Creating additional connections for node {src_node}")
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
                logger.debug(f"Added edge: {src_node}:{chosen_node}")
        logger.debug(f"Node {src_node} edges: {graph.edges(src_node)}")

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
    with open(GRAPH_SCHEMA_PATH) as schema_file:
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
