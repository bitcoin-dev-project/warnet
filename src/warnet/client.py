import logging
import docker
from test_framework.message_capture_parser import process_blob
from warnet.rpc_utils import bitcoin_rpc


def get_node(client: docker.DockerClient, node_id: int, network_name: str):
    """
    Fetch a node (container) from a network by its id.
    """
    network = client.networks.get(network_name)

    for container in network.containers:
        if container.name == f"{network_name}_{node_id}":
            return container

    raise ValueError(f"Container with name or ID '{node_id}' not found in network '{network_name}'.")


def get_bitcoin_debug_log(node: int, network="warnet"):
    d = docker.from_env()
    node = get_node(d, node, network)
    data, stat = node.get_archive("/root/.bitcoin/regtest/debug.log")
    out = ""
    for chunk in data:
        out += chunk.decode()
    # slice off tar archive header
    out = out[512:]
    # slice off end padding
    out = out[:stat["size"]]
    return out


def get_bitcoin_cli(node: int , method: str, params=None, network="warnet"):
    d = docker.from_env()
    node = get_node(d, node, network)
    return bitcoin_rpc(node, method, params)


def get_messages(src_node: int, dst_node: int, network: str = "warnet"):
    d = docker.from_env()
    src_node = get_node(d, src_node, network)
    dst_node = get_node(d, dst_node, network)
    # start with the IP of the peer
    dst_ip = dst_node.attrs["NetworkSettings"]["Networks"][network]["IPAddress"]
    # find the corresponding message capture folder
    # (which may include the internal port if connection is inbound)
    exit_code, dirs = src_node.exec_run("ls /root/.bitcoin/regtest/message_capture")
    dirs = dirs.decode().splitlines()
    messages = []
    for dir_name in dirs:
        if dst_ip in dir_name:
            for file, outbound in [["msgs_recv.dat", False], ["msgs_sent.dat", True]]:
                data, stat = src_node.get_archive(f"/root/.bitcoin/regtest/message_capture/{dir_name}/{file}")
                blob = b''
                for chunk in data:
                    blob += chunk
                # slice off tar archive header
                blob = blob[512:]
                # slice off end padding
                blob = blob[:stat["size"]]
                # parse
                json = process_blob(blob, outbound)
                messages = messages + json
    messages.sort(key=lambda x: x["time"])
    return messages


def stop_network(network: str = "warnet"):
    d = docker.from_env()
    network = d.networks.get(network)
    containers = network.containers
    for c in containers:
        logging.info(f"stopping container: {c.name}")
        c.stop()
    return True

def wipe_network(network: str = "warnet"):
    d = docker.from_env()
    network = d.networks.get(network)
    containers = network.containers
    for c in containers:
        logging.warning(f"removing container: {c.name}")
        c.remove()
    logging.warning(f"removing docker network: {network}")
    network.remove()
    return True
