import concurrent.futures
import logging
import threading
from typing import List, Optional

import docker

from warnet.utils import parse_raw_messages
from warnet.tank import Tank

logger = logging.getLogger("warnet.client")


def get_bitcoin_debug_log(network: str, index: int) -> str:
    tank = Tank.from_docker_env(network, index)
    subdir = "/" if tank.bitcoin_network == "main" else f"{tank.bitcoin_network}/"
    data, stat = tank.container.get_archive(f"/root/.bitcoin/{subdir}debug.log")
    out = ""
    for chunk in data:
        out += chunk.decode()
    # slice off tar archive header
    out = out[512:]
    # slice off end padding
    out = out[: stat["size"]]
    return out


def get_bitcoin_cli(network: str, index: int, method: str, params=None) -> str:
    tank = Tank.from_docker_env(network, index)
    return tank.exec(
        f"bitcoin-cli {method} {' '.join(map(str, params))}"
    ).output.decode()


def get_messages(network: str, src_index: int, dst_index: int) -> List[Optional[str]]:
    src_node = Tank.from_docker_env(network, src_index)
    dst_node = Tank.from_docker_env(network, dst_index)
    # start with the IP of the peer
    dst_ip = dst_node.ipv4
    # find the corresponding message capture folder
    # (which may include the internal port if connection is inbound)
    subdir = (
        "/" if src_node.bitcoin_network == "main" else f"{src_node.bitcoin_network}/"
    )
    exit_code, dirs = src_node.exec(f"ls /root/.bitcoin/{subdir}message_capture")
    dirs = dirs.decode().splitlines()
    messages = []
    for dir_name in dirs:
        if dst_ip in dir_name:
            for file, outbound in [["msgs_recv.dat", False], ["msgs_sent.dat", True]]:
                data, stat = src_node.container.get_archive(
                    f"/root/.bitcoin/{subdir}message_capture/{dir_name}/{file}"
                )
                blob = b""
                for chunk in data:
                    blob += chunk
                # slice off tar archive header
                blob = blob[512:]
                # slice off end padding
                blob = blob[: stat["size"]]
                # parse
                json = parse_raw_messages(blob, outbound)
                messages = messages + json
    messages.sort(key=lambda x: x["time"])
    return messages


def stop_container(c):
    logger.info(f"stopping container: {c.name}")
    c.stop()

def stop_network(network="warnet") -> bool:
    """
    Stop all containers in the network in parallel using a background thread
    """
    def thread_stop():
        d = docker.from_env()
        network_obj = d.networks.get(network)
        containers = network_obj.containers

        with concurrent.futures.ThreadPoolExecutor() as executor:
            executor.map(stop_container, containers)

    threading.Thread(target=thread_stop).start()
    return True


def remove_container(c):
    logger.warning(f"removing container: {c.name}")
    c.remove()

def remove_network(network_name="warnet") -> bool:
    def thread_remove_network():
        d = docker.from_env()
        network = d.networks.get(network_name)
        containers = network.containers

        with concurrent.futures.ThreadPoolExecutor() as executor:
            executor.map(stop_container, containers)

        # Use a second executor to ensure all stops complete before removes
        with concurrent.futures.ThreadPoolExecutor() as executor:
            executor.map(remove_container, containers)

    threading.Thread(target=thread_remove_network).start()
    return True

