import json
import re

import click

from .util import run_command


@click.group(name="bitcoin")
def bitcoin():
    """Control running bitcoin nodes"""


@bitcoin.command(context_settings={"ignore_unknown_options": True})
@click.argument("node", type=int)
@click.argument("method", type=str)
@click.argument("params", type=str, nargs=-1)  # this will capture all remaining arguments
@click.option("--network", default="warnet", show_default=True)
def rpc(node, method, params, network):
    """
    Call bitcoin-cli <method> [params] on <node> in [network]
    """
    if params:
        cmd = f"kubectl exec warnet-tank-{node} -- bitcoin-cli -regtest -rpcuser='user' -rpcpassword='password' {method} {' '.join(map(str, params))}"
    else:
        cmd = f"kubectl exec warnet-tank-{node} -- bitcoin-cli -regtest -rpcuser='user' -rpcpassword='password' {method}"
    run_command(cmd)


@bitcoin.command()
@click.argument("node", type=int, required=True)
@click.option("--network", default="warnet", show_default=True)
def debug_log(node, network):
    """
    Fetch the Bitcoin Core debug log from <node> in [network]
    """
    cmd = f"kubectl logs warnet-tank-{node}"
    run_command(cmd)


# @bitcoin.command()
# @click.argument("node_a", type=int, required=True)
# @click.argument("node_b", type=int, required=True)
# @click.option("--network", default="warnet", show_default=True)
# def messages(node_a, node_b, network):
#     """
#     Fetch messages sent between <node_a> and <node_b> in [network]
#     """
#     print(rpc_call("tank_messages", {"network": network, "node_a": node_a, "node_b": node_b}))
#
#

@bitcoin.command()
@click.argument("pattern", type=str, required=True)
@click.option("--show-k8s-timestamps", is_flag=True, default=False, show_default=True)
@click.option("--no-sort", is_flag=True, default=False, show_default=True)
@click.option("--network", default="warnet", show_default=True)
def grep_logs(pattern, network, show_k8s_timestamps, no_sort):
    """
    Grep combined bitcoind logs using regex <pattern>
    """

    # Get all pods in the namespace
    command = f"kubectl get pods -n {network} -o json"
    pods_json = run_command(command, return_output=True)

    if pods_json is False:
        print("Error: Failed to get pods information")
        return

    try:
        pods = json.loads(pods_json)
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        return

    matching_logs = []

    for pod in pods.get("items", []):
        pod_name = pod.get("metadata", {}).get("name", "")
        if "warnet" in pod_name:
            # Get container names for this pod
            containers = pod.get("spec", {}).get("containers", [])
            if not containers:
                continue

            # Use the first container name
            container_name = containers[0].get("name", "")
            if not container_name:
                continue

            # Get logs from the specific container
            command = f"kubectl logs {pod_name} -c {container_name} -n {network} --timestamps"
            logs = run_command(command, return_output=True)

            if logs is not False:
                # Process logs
                for log_entry in logs.splitlines():
                    if re.search(pattern, log_entry):
                        matching_logs.append((log_entry, pod_name))

    # Sort logs if needed
    if not no_sort:
        matching_logs.sort(key=lambda x: x[0])

    # Print matching logs
    for log_entry, pod_name in matching_logs:
        try:
            # Split the log entry into Kubernetes timestamp, Bitcoin timestamp, and the rest of the log
            k8s_timestamp, rest = log_entry.split(" ", 1)
            bitcoin_timestamp, log_message = rest.split(" ", 1)

            # Format the output based on the show_k8s_timestamps option
            if show_k8s_timestamps:
                print(f"{pod_name}: {k8s_timestamp} {bitcoin_timestamp} {log_message}")
            else:
                print(f"{pod_name}: {bitcoin_timestamp} {log_message}")
        except ValueError:
            # If we can't parse the timestamps, just print the original log entry
            print(f"{pod_name}: {log_entry}")

    return matching_logs
