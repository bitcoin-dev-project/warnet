import yaml
import subprocess
import logging
import networkx as nx
from .prometheus import generate_prometheus_config

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


def generate_docker_compose(graph_file: str):
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

    graph = nx.read_graphml(graph_file, node_type=int)
    nodes = [graph.nodes[node] for node in graph.nodes()]
    generate_prometheus_config(len(nodes))

    services = {
        "prometheus": {
            "image": "prom/prometheus:latest",
            "container_name": "prometheus",
            "ports": ["9090:9090"],
            "volumes": ["./prometheus.yml:/etc/prometheus/prometheus.yml"],
            "command": ["--config.file=/etc/prometheus/prometheus.yml"],
            "networks": [
                "warnet_network"
            ]
        },
        "node-exporter": {
            "image": "prom/node-exporter:latest",
            "container_name": "node-exporter",
            "volumes": [
                "/proc:/host/proc:ro",
                "/sys:/host/sys:ro",
                "/:/rootfs:ro"
            ],
            "command": ["--path.procfs=/host/proc", "--path.sysfs=/host/sys"],
            "networks": [
                "warnet_network"
            ]
        },
        "grafana": {
            "image": "grafana/grafana:latest",
            "container_name": "grafana",
            "ports": ["3000:3000"],
            "volumes": ["grafana-storage:/var/lib/grafana"],
            "networks": [
                "warnet_network"
            ]
        }
    }
    volumes = {
        "grafana-storage": None,
    }

    for i, node in enumerate(nodes):
        version = node["version"]

        services[f"bitcoin-node-{i}"] = {
            "container_name": f"warnet_{i}",
            "build": {
                "context": ".",
                "dockerfile": "Dockerfile",
                "args": {
                    "ARCH": arch,
                    "BITCOIN_VERSION": version,
                    "BITCOIN_URL": f"https://bitcoincore.org/bin/bitcoin-core-{version}/bitcoin-{version}-{arch}-linux-gnu.tar.gz"
                }
            },
            "volumes": [
                f"./config/bitcoin.conf:/root/.bitcoin/bitcoin.conf"
            ],
            "networks": [
                "warnet_network"
            ]
        }
        services[f"prom-exporter-node-{i}"] = {
            "image": "jvstein/bitcoin-prometheus-exporter",
            "container_name": f"exporter-node-{i}",
            "environment": {
                "BITCOIN_RPC_HOST": f"bitcoin-node-{i}",
                "BITCOIN_RPC_PORT": 18443,
                "BITCOIN_RPC_USER": "btc",
                "BITCOIN_RPC_PASSWORD": "passwd",
            },
            "ports": [f"{8335 + i}:9332"],
            "networks": [
                "warnet_network"
            ]
        }

    compose_config = {
        "version": "3.8",
        "services": services,
        "volumes": volumes,
        "networks": {
            "warnet_network": {
                "name": "warnet_network",
                "driver": "bridge"
            }
        }
    }

    try:
        with open("docker-compose.yml", "w") as file:
            yaml.dump(compose_config, file)
    except Exception as e:
        logging.error(f"An error occurred while writing to docker-compose.yml: {e}")


