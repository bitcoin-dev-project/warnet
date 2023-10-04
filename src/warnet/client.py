import concurrent.futures
import logging
import threading
from datetime import datetime
from typing import List, Optional, Any, Dict

import docker

from warnet.utils import parse_raw_messages
from warnet.warnet import Warnet

logger = logging.getLogger("warnet.client")


def get_bitcoin_debug_log(network: str, index: int) -> str:
    warnet = Warnet.from_network(network)
    docker = warnet.docker
    container_name = warnet.tanks[index].container_name
    now = datetime.utcnow()

    logs = docker.api.logs(
        container=container_name,
        stdout=True,
        stderr=True,
        stream=False,
        until=now,
    )
    return logs.decode('utf-8')


def get_bitcoin_cli(network: str, index: int, method: str, params=None) -> str:
    warnet = Warnet.from_network(network)
    tank = warnet.tanks[index]
    if params:
        cmd = f"bitcoin-cli {method} {' '.join(map(str, params))}"
    else:
        cmd = f"bitcoin-cli {method}"
    return tank.exec(cmd=cmd, user="bitcoin")


def get_messages(
    network: str, src_index: int, dst_index: int
) -> List[Optional[Dict[str, Any]]]:
    warnet = Warnet.from_network(network)
    src_node = warnet.tanks[src_index]
    dst_node = warnet.tanks[dst_index]
    # start with the IP of the peer
    dst_ip = dst_node.ipv4
    # find the corresponding message capture folder
    # (which may include the internal port if connection is inbound)
    subdir = (
        "/" if src_node.bitcoin_network == "main" else f"{src_node.bitcoin_network}/"
    )
    dirs = src_node.exec(f"ls /home/bitcoin/.bitcoin/{subdir}message_capture")
    dirs = dirs.splitlines()
    messages = []
    for dir_name in dirs:
        if dst_ip in dir_name:
            for file, outbound in [["msgs_recv.dat", False], ["msgs_sent.dat", True]]:
                data, stat = src_node.container.get_archive(
                    f"/home/bitcoin/.bitcoin/{subdir}message_capture/{dir_name}/{file}"
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


def compose_down(network="warnet") -> bool:
    """
    Run docker-compose down on a warnet
    """
    wn = Warnet.from_network(network)
    wn.docker_compose_down()
    return True
