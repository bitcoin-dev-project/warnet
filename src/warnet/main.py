from jsonrpcserver import method, serve, Success
import logging
import docker
import warnet
from test_framework.message_capture_parser import process_blob
from warnet.rpc_utils import bitcoin_rpc

BITCOIN_GRAPH_FILE = "./graphs/basic3.graphml"

logging.basicConfig(level=logging.INFO)


@method
def run_warnet():
    d = docker.from_env()
    warnet.delete_containers(d)
    warnet.generate_docker_compose(BITCOIN_GRAPH_FILE)
    warnet.docker_compose()
    warnet.connect_edges(d, BITCOIN_GRAPH_FILE)
    return Success("warnet running")


@method
def get_debug_log(node):
    d = docker.from_env()
    c = d.containers.get(f"warnet_{node}")
    data, stat = c.get_archive("/root/.bitcoin/regtest/debug.log")
    out = ""
    for chunk in data:
        out += chunk.decode()
    # slice off tar archive header
    out = out[512:]
    # slice off end padding
    out = out[: stat["size"]]
    return Success(out)


@method
def get_bitcoin_cli(node, method, params=None):
    d = docker.from_env()
    c = d.containers.get(f"warnet_{node}")
    return Success(bitcoin_rpc(c, method, params))


@method
def get_messages(src, dst):
    d = docker.from_env()
    src = d.containers.get(f"warnet_{src}")
    dst = d.containers.get(f"warnet_{dst}")
    # start with the IP of the peer
    dst_ip = dst.attrs["NetworkSettings"]["Networks"]["warnet"]["IPAddress"]
    # find the corresponding message capture folder
    # (which may include the internal port if connection is inbound)
    exit_code, dirs = src.exec_run("ls /root/.bitcoin/regtest/message_capture")
    dirs = dirs.decode().splitlines()
    messages = []
    for dir_name in dirs:
        if dst_ip in dir_name:
            for file, outbound in [["msgs_recv.dat", False], ["msgs_sent.dat", True]]:
                data, stat = src.get_archive(
                    f"/root/.bitcoin/regtest/message_capture/{dir_name}/{file}"
                )
                blob = b""
                for chunk in data:
                    blob += chunk
                # slice off tar archive header
                blob = blob[512:]
                # slice off end padding
                blob = blob[: stat["size"]]
                # parse
                json = process_blob(blob, outbound)
                messages = messages + json
    messages.sort(key=lambda x: x["time"])
    return Success(messages)


@method
def stop_network():
    d = docker.from_env()
    network = d.networks.get("warnet")
    containers = network.containers
    for c in containers:
        print(f"stopping container: {c.name}")
        c.stop()
        print(f"removing container: {c.name}")
        c.remove()
    print("removing network: warnet")
    network.remove()
    return Success(True)


def main():
    serve()

if __name__ == "__main__":
    main()
