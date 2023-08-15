import yaml

base_rpc_port = 18000
base_p2p_port = 18001


# def parse_config():
#     with open("config.yaml", "r") as file:
#         return yaml.safe_load(file)


def generate_docker_compose(version, edge, node_count):
    # node_count = config.get("node", {}).get("count", 1)
    # version = config.get("node", {}).get("version", "latest")

    # version is a list of versions
    # parse the version for the docker-compose file

    services = {}
    c = 33
    for i in range(node_count):
        services[f"bitcoin-node-{i}"] = {
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
