import json
import os
import re
import sys
from datetime import datetime
from io import BytesIO
from typing import Optional

import click
from test_framework.messages import ser_uint256
from test_framework.p2p import MESSAGEMAP
from urllib3.exceptions import MaxRetryError

from .constants import BITCOINCORE_CONTAINER
from .k8s import get_default_namespace_or, get_mission, pod_log
from .process import run_command


@click.group(name="bitcoin")
def bitcoin():
    """Control running bitcoin nodes"""


@bitcoin.command(context_settings={"ignore_unknown_options": True})
@click.argument("tank", type=str)
@click.argument("method", type=str)
@click.argument("params", type=str, nargs=-1)  # this will capture all remaining arguments
@click.option("--namespace", default=None, show_default=True)
def rpc(tank: str, method: str, params: list[str], namespace: Optional[str]):
    """
    Call bitcoin-cli <method> [params] on <tank pod name>
    """
    try:
        result = _rpc(tank, method, params, namespace)
    except Exception as e:
        print(f"{e}")
        sys.exit(1)
    print(result)


def _rpc(tank: str, method: str, params: list[str], namespace: Optional[str] = None):
    # bitcoin-cli should be able to read bitcoin.conf inside the container
    # so no extra args like port, chain, username or password are needed
    namespace = get_default_namespace_or(namespace)

    # Reconstruct JSON parameters that may have been split by shell parsing
    # This fixes issues where JSON arrays like ["network"] get split into separate arguments
    reconstructed_params = _reconstruct_json_params(params)

    if reconstructed_params:
        # Process each parameter to handle different data types correctly for bitcoin-cli
        processed_params = []
        for param in reconstructed_params:
            # Handle boolean and primitive values that should not be quoted
            if param.lower() in ["true", "false", "null"]:
                processed_params.append(param.lower())
            elif param.isdigit() or (param.startswith("-") and param[1:].isdigit()):
                # Numeric values (integers, negative numbers)
                processed_params.append(param)
            else:
                try:
                    # Try to parse as JSON to handle complex data structures
                    parsed_json = json.loads(param)
                    if isinstance(parsed_json, list):
                        # If it's a list, extract the elements and add them individually
                        # This ensures bitcoin-cli receives each list element as a separate argument
                        for element in parsed_json:
                            if isinstance(element, str):
                                processed_params.append(f'"{element}"')
                            else:
                                processed_params.append(str(element))
                    elif isinstance(parsed_json, dict):
                        # If it's a dict, pass it as a single JSON argument
                        # bitcoin-cli expects objects to be passed as JSON strings
                        processed_params.append(param)
                    else:
                        # If it's a primitive value (number, boolean), pass it as-is
                        processed_params.append(str(parsed_json))
                except json.JSONDecodeError:
                    # Not valid JSON, pass as-is (treat as plain string)
                    processed_params.append(param)

        cmd = f"kubectl -n {namespace} exec {tank} --container {BITCOINCORE_CONTAINER} -- bitcoin-cli {method} {' '.join(map(str, processed_params))}"
    else:
        cmd = f"kubectl -n {namespace} exec {tank} --container {BITCOINCORE_CONTAINER} -- bitcoin-cli {method}"
    return run_command(cmd)


@bitcoin.command()
@click.argument("tank", type=str, required=True)
@click.option("--namespace", default=None, show_default=True)
def debug_log(tank: str, namespace: Optional[str]):
    """
    Fetch the Bitcoin Core debug log from <tank pod name>
    """
    namespace = get_default_namespace_or(namespace)
    cmd = f"kubectl logs {tank} --namespace {namespace}"
    try:
        print(run_command(cmd))
    except Exception as e:
        print(f"{e}")


@bitcoin.command()
@click.argument("pattern", type=str, required=True)
@click.option("--show-k8s-timestamps", is_flag=True, default=False, show_default=True)
@click.option("--no-sort", is_flag=True, default=False, show_default=True)
def grep_logs(pattern: str, show_k8s_timestamps: bool, no_sort: bool):
    """
    Grep combined bitcoind logs using regex <pattern>
    """

    try:
        tanks = get_mission("tank")
    except MaxRetryError as e:
        print(f"{e}")
        sys.exit(1)

    matching_logs = []
    longest_namespace_len = 0

    for tank in tanks:
        if len(tank.metadata.namespace) > longest_namespace_len:
            longest_namespace_len = len(tank.metadata.namespace)

        pod_name = tank.metadata.name
        logs = pod_log(pod_name, BITCOINCORE_CONTAINER)

        if logs is not False:
            try:
                for line in logs:
                    log_entry = line.decode("utf-8").rstrip()
                    if re.search(pattern, log_entry):
                        matching_logs.append((log_entry, tank.metadata.namespace, pod_name))
            except Exception as e:
                print(e)
            except KeyboardInterrupt:
                print("Interrupted streaming log!")

    # Sort logs if needed
    if not no_sort:
        matching_logs.sort(key=lambda x: x[0])

    # Print matching logs
    for log_entry, namespace, pod_name in matching_logs:
        try:
            # Split the log entry into Kubernetes timestamp, Bitcoin timestamp, and the rest of the log
            k8s_timestamp, rest = log_entry.split(" ", 1)
            bitcoin_timestamp, log_message = rest.split(" ", 1)

            # Format the output based on the show_k8s_timestamps option
            if show_k8s_timestamps:
                print(
                    f"{pod_name} {namespace:<{longest_namespace_len}} {k8s_timestamp} {bitcoin_timestamp} {log_message}"
                )
            else:
                print(
                    f"{pod_name} {namespace:<{longest_namespace_len}} {bitcoin_timestamp} {log_message}"
                )
        except ValueError:
            # If we can't parse the timestamps, just print the original log entry
            print(f"{pod_name}: {log_entry}")

    return matching_logs


@bitcoin.command()
@click.argument("tank_a", type=str, required=True)
@click.argument("tank_b", type=str, required=True)
@click.option("--chain", default="regtest", show_default=True)
def messages(tank_a: str, tank_b: str, chain: str):
    """
    Fetch messages sent between <tank_a pod name> and <tank_b pod name> in [chain]

    Optionally, include a namespace like so: tank-name.namespace
    """

    def parse_name_and_namespace(tank: str) -> tuple[str, Optional[str]]:
        tank_split = tank.split(".")
        try:
            namespace = tank_split[1]
        except IndexError:
            namespace = None
        return tank_split[0], namespace

    tank_a_split = tank_a.split(".")
    tank_b_split = tank_b.split(".")
    if len(tank_a_split) > 2 or len(tank_b_split) > 2:
        click.secho("Accepted formats: tank-name OR tank-name.namespace")
        click.secho(f"Foramts found: {tank_a} {tank_b}")
        sys.exit(1)

    tank_a, namespace_a = parse_name_and_namespace(tank_a)
    tank_b, namespace_b = parse_name_and_namespace(tank_b)

    try:
        namespace_a = get_default_namespace_or(namespace_a)
        namespace_b = get_default_namespace_or(namespace_b)

        # Get the messages
        messages = get_messages(
            tank_a, tank_b, chain, namespace_a=namespace_a, namespace_b=namespace_b
        )

        if not messages:
            print(
                f"No messages found between {tank_a} ({namespace_a}) and {tank_b} ({namespace_b})"
            )
            return

        # Process and print messages
        for message in messages:
            if not (message.get("time") and isinstance(message["time"], (int, float))):
                continue

            timestamp = datetime.utcfromtimestamp(message["time"] / 1e6).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            direction = ">>>" if message.get("outbound", False) else "<<<"
            msgtype = message.get("msgtype", "")
            body_dict = message.get("body", {})

            if not isinstance(body_dict, dict):
                continue

            body_str = ", ".join(f"{key}: {value}" for key, value in body_dict.items())
            print(f"{timestamp} {direction} {msgtype} {body_str}")

    except Exception as e:
        print(f"Error fetching messages between nodes {tank_a} and {tank_b}: {e}")


def get_messages(tank_a: str, tank_b: str, chain: str, namespace_a: str, namespace_b: str):
    """
    Fetch messages from the message capture files
    """
    subdir = "" if chain == "main" else f"{chain}/"
    base_dir = f"/root/.bitcoin/{subdir}message_capture"

    # Get the IP of node_b
    cmd = f"kubectl get pod {tank_b} -o jsonpath='{{.status.podIP}}' --namespace {namespace_b}"
    tank_b_ip = run_command(cmd).strip()

    # Get the service IP of node_b
    cmd = (
        f"kubectl get service {tank_b} -o jsonpath='{{.spec.clusterIP}}' --namespace {namespace_b}"
    )
    tank_b_service_ip = run_command(cmd).strip()

    # List directories in the message capture folder
    cmd = f"kubectl exec {tank_a} --namespace {namespace_a} -- ls {base_dir}"

    dirs = run_command(cmd).splitlines()

    messages = []

    for dir_name in dirs:
        if tank_b_ip in dir_name or tank_b_service_ip in dir_name:
            for file, outbound in [["msgs_recv.dat", False], ["msgs_sent.dat", True]]:
                file_path = f"{base_dir}/{dir_name}/{file}"
                # Fetch the file contents from the container
                cmd = f"kubectl exec {tank_a} --namespace {namespace_a} -- cat {file_path}"
                import subprocess

                blob = subprocess.run(
                    cmd, shell=True, capture_output=True, executable="bash"
                ).stdout

                # Parse the blob
                json = parse_raw_messages(blob, outbound)
                messages = messages + json

    messages.sort(key=lambda x: x["time"])
    return messages


# This function is a hacked-up copy of process_file() from
# Bitcoin Core contrib/message-capture/message-capture-parser.py
def parse_raw_messages(blob: bytes, outbound: bool):
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
            # print(f"WARNING - Unrecognized message type {msgtype}", file=sys.stderr)
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
            # print("WARNING - Unable to deserialize message", file=sys.stderr)
            continue

        # Convert body of message into a jsonable object
        if length:
            msg_dict["body"] = to_jsonable(msg)
        messages.append(msg_dict)
    return messages


def to_jsonable(obj: str):
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


def _reconstruct_json_params(params: list[str]) -> list[str]:
    """
    Reconstruct JSON parameters that may have been split by shell parsing.

    This function detects when parameters look like they should be JSON and
    reconstructs them properly. For example:
    - ['[network]'] -> ['["network"]']
    - ['[network,', 'message_type]'] -> ['["network", "message_type"]']
    - ['[{"key":', '"value"}]'] -> ['[{"key": "value"}]']

    This fixes the issue described in GitHub issue #714 where shell parsing
    breaks JSON parameters into separate arguments.
    """
    if not params:
        return params

    reconstructed = []
    i = 0

    while i < len(params):
        param = params[i]

        # Check if this looks like the start of a JSON array or object
        # that was split across multiple arguments by shell parsing
        if (param.startswith("[") and not param.endswith("]")) or (
            param.startswith("{") and not param.endswith("}")
        ):
            # This is the start of a JSON structure, collect all parts
            json_parts = [param]
            i += 1

            # Collect all parts until we find the closing bracket/brace
            while i < len(params):
                next_param = params[i]
                json_parts.append(next_param)

                if (param.startswith("[") and next_param.endswith("]")) or (
                    param.startswith("{") and next_param.endswith("}")
                ):
                    break
                i += 1

            # Reconstruct the JSON string by joining all parts
            json_str = " ".join(json_parts)

            # Validate that it's valid JSON before adding
            try:
                json.loads(json_str)
                reconstructed.append(json_str)
            except json.JSONDecodeError:
                # If it's not valid JSON, add parts as separate parameters
                # This preserves the original behavior for non-JSON arguments
                reconstructed.extend(json_parts)

        elif param.startswith("[") and param.endswith("]"):
            # Single parameter that looks like JSON array
            # Check if it's missing quotes around string elements
            if "[" in param and "]" in param and '"' not in param:
                # This looks like [value] without quotes, try to add them
                inner_content = param[1:-1]  # Remove brackets
                if "," in inner_content:
                    # Multiple values: [val1, val2] -> ["val1", "val2"]
                    values = [v.strip() for v in inner_content.split(",")]
                    quoted_values = [f'"{v}"' for v in values]
                    reconstructed_param = f"[{', '.join(quoted_values)}]"
                else:
                    # Single value: [value] -> ["value"]
                    reconstructed_param = f'["{inner_content.strip()}"]'

                # Validate the reconstructed JSON
                try:
                    json.loads(reconstructed_param)
                    reconstructed.append(reconstructed_param)
                except json.JSONDecodeError:
                    # If reconstruction fails, keep original parameter
                    reconstructed.append(param)
            else:
                # Already has quotes or is not a string array
                try:
                    json.loads(param)
                    reconstructed.append(param)
                except json.JSONDecodeError:
                    reconstructed.append(param)

        else:
            # Regular parameter, add as-is
            reconstructed.append(param)

        i += 1

    return reconstructed
