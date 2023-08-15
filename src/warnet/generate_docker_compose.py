import yaml
import subprocess
import logging

BASE_RPC_PORT = 18000
BASE_P2P_PORT = 18001

logging.basicConfig(level=logging.INFO)

def get_architecture():
    """
    Get the architecture of the machine.

    :return: The architecture of the machine or None if an error occurred
    """
    try:
        result = subprocess.run(['uname', '-m'], stdout=subprocess.PIPE)
        architecture = result.stdout.decode('utf-8').strip()
        if architecture == "arm64":
            architecture = "aarch64"
        return architecture
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return None

def generate_docker_compose(version, node_count):
    """
    Generate a docker-compose.yml file for the given graph.

    :param version: A list of Bitcoin Core versions
    :param node_count: The number of nodes in the graph
    """
    arch = get_architecture()
    if arch is not None:
        logging.info(f"Detected architecture: {arch}")
    else:
        raise Exception("Failed to detect architecture.")

    services = {}
    c = 33
    for i in range(node_count):
        services[f"bitcoin-node-{i}"] = {
            "container_name": f"warnet_{i}",
            "build": {
                "context": ".",
                "dockerfile": "Dockerfile",
                "args": {
                    "ARCH": arch,
                    "BITCOIN_VERSION": version[i],
                    "BITCOIN_URL": f"https://bitcoincore.org/bin/bitcoin-core-{version[i]}/bitcoin-{version[i]}-{arch}-linux-gnu.tar.gz"
                }
            },
            "volumes": [
                f"./config/bitcoin.conf:/root/.bitcoin/bitcoin.conf"
            ]
        }
        c = c + 2

    compose_config = {
        "version": "3.8",
        "services": services
    }

    try:
        with open("docker-compose.yml", "w") as file:
            yaml.dump(compose_config, file)
    except Exception as e:
        logging.error(f"An error occurred while writing to docker-compose.yml: {e}")

