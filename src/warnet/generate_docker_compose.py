import yaml
import subprocess
import logging

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

    services = {
        "prometheus": {
            "image": "prom/prometheus:latest",
            "container_name": "prometheus",
            "ports": ["9090:9090"],
            "volumes": ["./prometheus.yml:/etc/prometheus/prometheus.yml"],
            "command": ["--config.file=/etc/prometheus/prometheus.yml"]
        },
        "node-exporter": {
            "image": "prom/node-exporter:latest",
            "container_name": "node-exporter",
            "volumes": [
                "/proc:/host/proc:ro",
                "/sys:/host/sys:ro",
                "/:/rootfs:ro"
            ],
            "command": ["--path.procfs=/host/proc", "--path.sysfs=/host/sys"]
        },
        "grafana": {
            "image": "grafana/grafana:latest",
            "container_name": "grafana",
            "ports": ["3000:3000"],
            "volumes": ["grafana-storage:/var/lib/grafana"]
        }
    }
    volumes = {
        "grafana-storage": None,
    }

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


def generate_prometheus_config(node_count):
    """
    Generate a prometheus.yml file based on the number of Bitcoin nodes.

    :param node_count: The number of Bitcoin nodes
    """
    config = {
        "global": {
            "scrape_interval": "15s"
        },
        "scrape_configs": [
            {
                "job_name": "prometheus",
                "scrape_interval": "5s",
                "static_configs": [{"targets": ["localhost:9090"]}]
            },
            {
                "job_name": "node-exporter",
                "scrape_interval": "5s",
                "static_configs": [{"targets": ["node-exporter:9100"]}]
            },
            {
                "job_name": "cadvisor",
                "scrape_interval": "5s",
                "static_configs": [{"targets": ["cadvisor:8080"]}]
            }
        ]
    }

    for i in range(node_count):
        config["scrape_configs"].append({
            "job_name": f"bitcoin-node-{i}",
            "scrape_interval": "5s",
            "static_configs": [{"targets": [f"exporter-node-{i}:9332"]}]
        })

    try:
        with open("prometheus.yml", "w") as file:
            yaml.dump(config, file)
    except Exception as e:
        logging.error(f"An error occurred while writing to prometheus.yml: {e}")

