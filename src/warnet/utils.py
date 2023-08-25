import functools
import ipaddress
import logging
import os
import random
import re
import subprocess
import sys
import time
from io import BytesIO
from test_framework.p2p import MESSAGEMAP
from test_framework.messages import ser_uint256

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
        ret = {}    # type: Any
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
        tmp_header_raw = blob[offset:offset+header_len]

        offset = offset + header_len
        if not tmp_header_raw:
            break
        tmp_header = BytesIO(tmp_header_raw)
        time = int.from_bytes(tmp_header.read(TIME_SIZE), "little")      # type: int
        msgtype = tmp_header.read(MSGTYPE_SIZE).split(b'\x00', 1)[0]     # type: bytes
        length = int.from_bytes(tmp_header.read(LENGTH_SIZE), "little")  # type: int

        # Start converting the message to a dictionary
        msg_dict = {}
        msg_dict["outbound"] = outbound
        msg_dict["time"] = time
        msg_dict["size"] = length   # "size" is less readable here, but more readable in the output

        msg_ser = BytesIO(blob[offset:offset+length])
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
            print(f"WARNING - Unable to deserialize message", file=sys.stderr)
            continue

        # Convert body of message into a jsonable object
        if length:
            msg_dict["body"] = to_jsonable(msg)
        messages.append(msg_dict)
    return messages
