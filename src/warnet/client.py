import logging
import docker
from test_framework.message_capture_parser import process_blob
from warnet.tank import Tank

def get_node(client: docker.DockerClient, node_id: int, network_name: str):
    """
    Fetch a node (container) from a network by its id.
    """
    network = client.networks.get(network_name)

    for container in network.containers:
        if container.name == f"{network_name}_{node_id}":
            return container

    raise ValueError(f"Container with name or ID '{node_id}' not found in network '{network_name}'.")

def get_bitcoin_debug_log(index: int):
    tank = Tank.from_docker_env(index)
    data, stat = tank.container.get_archive("/root/.bitcoin/regtest/debug.log")
    out = ""
    for chunk in data:
        out += chunk.decode()
    # slice off tar archive header
    out = out[512:]
    # slice off end padding
    out = out[:stat["size"]]
    return out

def get_bitcoin_cli(index: int, method: str, params=None):
    tank = Tank.from_docker_env(index)
    return tank.exec(f"bitcoin-cli {method} {' '.join(map(str, params))}").output.decode()

def get_messages(src_index: int, dst_index: int):
    src_node = Tank.from_docker_env(src_index)
    dst_node = Tank.from_docker_env(dst_index)
    # start with the IP of the peer
    dst_ip = dst_node.ipv4
    # find the corresponding message capture folder
    # (which may include the internal port if connection is inbound)
    exit_code, dirs = src_node.exec("ls /root/.bitcoin/regtest/message_capture")
    dirs = dirs.decode().splitlines()
    messages = []
    for dir_name in dirs:
        if dst_ip in dir_name:
            for file, outbound in [["msgs_recv.dat", False], ["msgs_sent.dat", True]]:
                data, stat = src_node.container.get_archive(f"/root/.bitcoin/regtest/message_capture/{dir_name}/{file}")
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

def stop_network():
    d = docker.from_env()
    network = d.networks.get("warnet")
    containers = network.containers
    for c in containers:
        logging.info(f"stopping container: {c.name}")
        c.stop()
    return True

def wipe_network():
    d = docker.from_env()
    network = d.networks.get("warnet")
    containers = network.containers
    for c in containers:
        logging.warning(f"removing container: {c.name}")
        c.remove()
    logging.warning(f"removing docker network: {network}")
    network.remove()
    return True
