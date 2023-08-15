import yaml
import subprocess

base_rpc_port = 18000
base_p2p_port = 18001


def get_architecture():
    try:
        result = subprocess.run(['uname', '-m'], stdout=subprocess.PIPE)
        architecture = result.stdout.decode('utf-8').strip()
        return architecture

    except Exception as e:
        print(f"An error occurred: {e}")
        return None


def generate_docker_compose(version, node_count):
    """
    Generate a docker-compose.yml file for the given graph
    :param version: A list of Bitcoin Core versions
    :param node_count: The number of nodes in the graph
    """
    arch = get_architecture()
    if arch is not None:
        print(f"Detected architecture: {arch}")
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
