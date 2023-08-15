import yaml

base_rpc_port = 18000
base_p2p_port = 18001

def generate_docker_compose(version, node_count):
    """
    Generate a docker-compose.yml file for the given graph
    :param version: A list of Bitcoin Core versions
    :param node_count: The number of nodes in the graph
    """
    services = {}
    c = 33
    for i in range(node_count):
        services[f"bitcoin-node-{i}"] = {
            "container_name": f"warnet_{i}",
            "build": {
                "context": ".",
                "dockerfile": "Dockerfile",
                "args": {
                    "BITCOIN_VERSION": version[i]
                }
            },
            "ports": [
                f"183{c}:18332",
                f"183{c+1}:18333"
            ],
            "volumes": [
                f"./config/bitcoin.conf:/root/.bitcoin/bitcoin.conf"
            ]
        }
        c = c + 2

    compose_config = {
        "version": "3.8",
        "services": services
    }

    with open("docker-compose.yml", "w") as file:
        yaml.dump(compose_config, file)
