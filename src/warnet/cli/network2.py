import os
import tempfile
from pathlib import Path

import click
import yaml

from .process import stream_command

NETWORK_DIR = Path("networks")
DEFAULT_NETWORK = "6_node_bitcoin"
NETWORK_FILE = "network.yaml"
DEFAULTS_FILE = "defaults.yaml"
HELM_COMMAND = "helm upgrade --install --create-namespace"
BITCOIN_CHART_LOCATION = "./resources/charts/bitcoincore"
NAMESPACE = "warnet"


@click.group(name="network2")
def network2():
    """Network commands"""


@network2.command()
@click.argument("network_name", default=DEFAULT_NETWORK)
@click.option("--network", default="warnet", show_default=True)
@click.option("--logging/--no-logging", default=False)
def start2(network_name: str, logging: bool, network: str):
    """Start a warnet with topology loaded from <network_name> into [network]"""
    full_path = os.path.join(NETWORK_DIR, network_name)
    network_file_path = os.path.join(full_path, NETWORK_FILE)
    defaults_file_path = os.path.join(full_path, DEFAULTS_FILE)

    network_file = {}
    with open(network_file_path) as f:
        network_file = yaml.safe_load(f)

    for node in network_file["nodes"]:
        print(f"Starting node: {node.get('name')}")
        try:
            temp_override_file_path = ""
            node_name = node.get("name")
            # all the keys apart from name
            node_config_override = {k: v for k, v in node.items() if k != "name"}

            cmd = f"{HELM_COMMAND} {node_name} {BITCOIN_CHART_LOCATION} --namespace {NAMESPACE} -f {defaults_file_path}"

            if node_config_override:
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".yaml", delete=False
                ) as temp_file:
                    yaml.dump(node_config_override, temp_file)
                    temp_override_file_path = temp_file.name
                cmd = f"{cmd} -f {temp_override_file_path}"

            if not stream_command(cmd):
                print(f"Failed to run Helm command: {cmd}")
                return
        except Exception as e:
            print(f"Error: {e}")
            return
        # finally:
        # if temp_override_file_path:
        #     Path(temp_override_file_path).unlink()
