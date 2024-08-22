import json
import os
import tempfile
from importlib.resources import files
from pathlib import Path

import click
import yaml
from rich import print

from .bitcoin import _rpc
from .k8s import (
    delete_namespace,
    get_mission,
    get_default_namespace,
)
from .process import stream_command

WAR_MANIFESTS = files("manifests")
NETWORK_DIR = Path("networks")
DEFAULT_NETWORK = "6_node_bitcoin"
NETWORK_FILE = "network.yaml"
DEFAULTS_FILE = "defaults.yaml"
HELM_COMMAND = "helm upgrade --install --create-namespace"
BITCOIN_CHART_LOCATION = "./resources/charts/bitcoincore"


@click.group(name="network")
def network():
    """Network commands"""


class Edge:
    def __init__(self, src: str, dst: str, data: dict[str, any]):
        self.src = src
        self.dst = dst
        self.data = data

    def to_dict(self):
        return {"src": self.src, "dst": self.dst, "data": self.data}


def edges_from_network_file(network_file: dict[str, any]) -> list[Edge]:
    edges = []
    for node in network_file["nodes"]:
        if "connect" in node:
            for connection in node["connect"]:
                edges.append(Edge(node["name"], connection, ""))
    return edges


def setup_logging_helm() -> bool:
    helm_commands = [
        "helm repo add grafana https://grafana.github.io/helm-charts",
        "helm repo add prometheus-community https://prometheus-community.github.io/helm-charts",
        "helm repo update",
        f"helm upgrade --install --namespace warnet-logging --create-namespace --values {WAR_MANIFESTS}/loki_values.yaml loki grafana/loki --version 5.47.2",
        "helm upgrade --install --namespace warnet-logging promtail grafana/promtail",
        "helm upgrade --install --namespace warnet-logging prometheus prometheus-community/kube-prometheus-stack --namespace warnet-logging --set grafana.enabled=false",
        f"helm upgrade --install --namespace warnet-logging loki-grafana grafana/grafana --values {WAR_MANIFESTS}/grafana_values.yaml",
    ]

    for command in helm_commands:
        if not stream_command(command):
            print(f"Failed to run Helm command: {command}")
            return False
    return True


@network.command()
@click.argument("network_name", default=DEFAULT_NETWORK)
@click.option("--network", default="warnet", show_default=True)
@click.option("--logging/--no-logging", default=False)
def start(network_name: str, logging: bool, network: str):
    """Start a warnet with topology loaded from <network_name> into [network]"""
    full_path = os.path.join(NETWORK_DIR, network_name)
    network_file_path = os.path.join(full_path, NETWORK_FILE)
    defaults_file_path = os.path.join(full_path, DEFAULTS_FILE)

    network_file = {}
    with open(network_file_path) as f:
        network_file = yaml.safe_load(f)

    namespace = get_default_namespace()

    for node in network_file["nodes"]:
        print(f"Starting node: {node.get('name')}")
        try:
            temp_override_file_path = ""
            node_name = node.get("name")
            # all the keys apart from name
            node_config_override = {k: v for k, v in node.items() if k != "name"}

            cmd = f"{HELM_COMMAND} {node_name} {BITCOIN_CHART_LOCATION} --namespace {namespace} -f {defaults_file_path}"

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
        finally:
            if temp_override_file_path:
                Path(temp_override_file_path).unlink()


@network.command()
def down():
    """Bring down a running warnet"""
    namespace = get_default_namespace()
    if delete_namespace(namespace) and delete_namespace("warnet-logging"):
        print("Warnet network has been successfully brought down and the namespaces deleted.")
    else:
        print("Failed to bring down warnet network or delete the namespaces.")


@network.command()
@click.option("--follow", "-f", is_flag=True, help="Follow logs")
def logs(follow: bool):
    """Get Kubernetes logs from the RPC server"""
    command = f"kubectl logs rpc-0{' --follow' if follow else ''}"
    stream_command(command)


@network.command()
def connected():
    """Determine if all p2p connections defined in graph are established"""
    print(_connected())


def _connected():
    tanks = get_mission("tank")
    for tank in tanks:
        # Get actual
        peerinfo = json.loads(_rpc(tank.metadata.name, "getpeerinfo", ""))
        manuals = 0
        for peer in peerinfo:
            if peer["connection_type"] == "manual":
                manuals += 1
        # Even if more edges are specifed, bitcoind only allows
        # 8 manual outbound connections
        if min(8, int(tank.metadata.annotations["init_peers"])) > manuals:
            print("Network not connected")
            return False
    print("Network connected")
    return True


@network.command()
def status():
    """Return pod status"""
    # TODO: make it a pretty table
    print(_status())


def _status():
    tanks = get_mission("tank")
    stats = []
    for tank in tanks:
        status = {
            "tank_index": tank.metadata.labels["app.kubernetes.io/instance"],
            "bitcoin_status": tank.status.phase.lower(),
        }
        stats.append(status)
    return stats
