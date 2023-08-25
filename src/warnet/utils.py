import functools
import ipaddress
import logging
import random
import re
import subprocess
import time

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
                    logging.error(f"rpc error:\n\t{e}")
                    retries += 1
                    if retries == max_retries:
                        raise e
                    delay = min(base_delay * (2 ** retries), max_delay)
                    logging.warning(f"retry in {delay} seconds...")
                    time.sleep(delay)
        return wrapper
    return decorator

def get_architecture():
    """
    Get the architecture of the machine.

    :return: The architecture of the machine or None if an error occurred
    """
    result = subprocess.run(['uname', '-m'], stdout=subprocess.PIPE)
    arch = result.stdout.decode('utf-8').strip()
    if arch == "arm64":
        arch = "aarch64"
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
        '0.0.0.0/8',
        '10.0.0.0/8',
        '100.64.0.0/10',
        '127.0.0.0/8',
        '169.254.0.0/16',
        '172.16.0.0/12',
        '192.0.0.0/24',
        '192.0.2.0/24',
        '192.88.99.0/24',
        '192.168.0.0/16',
        '198.18.0.0/15',
        '198.51.100.0/24',
        '203.0.113.0/24',
        '224.0.0.0/4'
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
        if not line or line.startswith('#'):
            continue

        if line.startswith('[') and line.endswith(']'):
            current_section = line[1:-1]
            result[current_section] = []
        elif '=' in line:
            key, value = line.split('=', 1)
            result[current_section].append((key.strip(), value.strip()))

    return result

def dump_bitcoin_conf(conf_dict):
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
    for (sub_key, sub_value) in values:
        result.append(f'{sub_key}={sub_value}')

    # Then print any named subsections
    for section, values in conf_dict.items():
        if section is not None:
            result.append(f'\n[{section}]')
        else:
            continue
        for (sub_key, sub_value) in values:
            result.append(f'{sub_key}={sub_value}')

    # Terminate file with newline
    return '\n'.join(result) + '\n'
