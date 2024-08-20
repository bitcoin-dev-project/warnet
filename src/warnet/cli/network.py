import tempfile
import xml.etree.ElementTree as ET
from importlib.resources import files
from pathlib import Path
from typing import Any, Dict, List

import click
import networkx as nx
import yaml
from rich import print

from .k8s import (
    apply_kubernetes_yaml,
    create_namespace,
    delete_namespace,
    deploy_base_configurations,
    run_command,
    set_kubectl_context,
)

DEFAULT_GRAPH_FILE = files("graphs").joinpath("default.graphml")
WAR_MANIFESTS = files("manifests")


@click.group(name="network")
def network():
    """Network commands"""


def read_graph_file(graph_file: Path) -> nx.Graph:
    with open(graph_file) as f:
        return nx.parse_graphml(f.read())


def generate_node_config(node: int, data: dict) -> str:
    base_config = """
regtest=1
checkmempool=0
acceptnonstdtxn=1
debuglogfile=0
logips=1
logtimemicros=1
capturemessages=1
fallbackfee=0.00001000
listen=1

[regtest]
rpcuser=user
rpcpassword=password
rpcport=18443
rpcallowip=0.0.0.0/0
rpcbind=0.0.0.0

zmqpubrawblock=tcp://0.0.0.0:28332
zmqpubrawtx=tcp://0.0.0.0:28333
"""
    node_specific_config = data.get("bitcoin_config", "").replace(",", "\n")
    return f"{base_config}\n{node_specific_config}"


def create_kubernetes_object(
    kind: str, metadata: Dict[str, Any], spec: Dict[str, Any] = None
) -> Dict[str, Any]:
    obj = {
        "apiVersion": "v1",
        "kind": kind,
        "metadata": metadata,
    }
    if spec is not None:
        obj["spec"] = spec
    return obj


def create_node_deployment(node: int, data: dict) -> Dict[str, Any]:
    image = data.get("image", "bitcoindevproject/bitcoin:27.0")
    version = data.get("version", "27.0")

    return create_kubernetes_object(
        kind="Pod",
        metadata={
            "name": f"warnet-tank-{node}",
            "namespace": "warnet",
            "labels": {"rank": "tank", "index": str(node)},
        },
        spec={
            "containers": [
                {
                    "name": "bitcoin",
                    "image": image,
                    "env": [{"name": "BITCOIN_VERSION", "value": version}],
                    "volumeMounts": [
                        {
                            "name": "config",
                            "mountPath": "/root/.bitcoin/bitcoin.conf",
                            "subPath": "bitcoin.conf",
                        }
                    ],
                }
            ],
            "volumes": [{"name": "config", "configMap": {"name": f"bitcoin-config-tank-{node}"}}],
        },
    )


def create_node_service(node: int) -> Dict[str, Any]:
    return create_kubernetes_object(
        kind="Service",
        metadata={"name": f"warnet-tank-{node}-service", "namespace": "warnet"},
        spec={
            "selector": {"app": "warnet", "node": str(node)},
            "ports": [{"port": 8333, "targetPort": 8333}],
        },
    )


def create_config_map(node: int, config: str) -> Dict[str, Any]:
    return create_kubernetes_object(
        kind="ConfigMap",
        metadata={
            "name": f"bitcoin-config-tank-{node}",
            "namespace": "warnet",
        },
        # Note: We're not passing a 'spec' here, as ConfigMaps don't have a spec
    )


def generate_kubernetes_yaml(graph: nx.Graph) -> List[Dict[str, Any]]:
    kubernetes_objects = [create_namespace()]

    for node, data in graph.nodes(data=True):
        config = generate_node_config(node, data)
        config_map = create_config_map(node, config)
        config_map["data"] = {"bitcoin.conf": config}  # Add data directly to the ConfigMap
        kubernetes_objects.extend(
            [
                config_map,
                create_node_deployment(node, data),
                create_node_service(node),
            ]
        )

    return kubernetes_objects


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
        if not run_command(command, stream_output=True):
            print(f"Failed to run Helm command: {command}")
            return False
    return True


@network.command()
@click.argument("graph_file", default=DEFAULT_GRAPH_FILE, type=click.Path())
@click.option("--network", default="warnet", show_default=True)
@click.option("--logging/--no-logging", default=False)
def start(graph_file: Path, logging: bool, network: str):
    """Start a warnet with topology loaded from a <graph_file> into [network]"""
    graph = read_graph_file(graph_file)
    kubernetes_yaml = generate_kubernetes_yaml(graph)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as temp_file:
        yaml.dump_all(kubernetes_yaml, temp_file)
        temp_file_path = temp_file.name

    try:
        if deploy_base_configurations() and apply_kubernetes_yaml(temp_file_path):
            print(f"Warnet '{network}' started successfully.")
            if not set_kubectl_context(network):
                print(
                    "Warning: Failed to set kubectl context. You may need to manually switch to the warnet namespace."
                )
            if logging and not setup_logging_helm():
                print("Failed to install Helm charts.")
        else:
            print(f"Failed to start warnet '{network}'.")
    finally:
        Path(temp_file_path).unlink()


@network.command()
@click.option("--network", default="warnet", show_default=True)
def down(network: str):
    """Bring down a running warnet named [network]"""
    if delete_namespace(network) and delete_namespace("warnet-logging"):
        print(f"Warnet '{network}' has been successfully brought down and the namespaces deleted.")
    else:
        print(f"Failed to bring down warnet '{network}' or delete the namespaces.")


@network.command()
@click.option("--follow", "-f", is_flag=True, help="Follow logs")
def logs(follow: bool):
    """Get Kubernetes logs from the RPC server"""
    command = f"kubectl logs rpc-0{' --follow' if follow else ''}"
    run_command(command, stream_output=follow)


@network.command()
@click.argument("graph_file", default=DEFAULT_GRAPH_FILE, type=click.Path())
@click.option("--output", "-o", default="warnet-deployment.yaml", help="Output YAML file")
def generate_yaml(graph_file: Path, output: str):
    """Generate a Kubernetes YAML file from a graph file for deploying warnet nodes."""
    graph = read_graph_file(graph_file)
    kubernetes_yaml = generate_kubernetes_yaml(graph)

    with open(output, "w") as f:
        yaml.dump_all(kubernetes_yaml, f)

    print(f"Kubernetes YAML file generated: {output}")


@network.command()
@click.argument("graph_file", default=DEFAULT_GRAPH_FILE, type=click.Path(exists=True))
def connect(graph_file: Path):
    """Connect nodes based on the edges defined in the graph file."""
    tree = ET.parse(graph_file)
    root = tree.getroot()
    edges = root.findall(".//{http://graphml.graphdrawing.org/xmlns}edge")

    for edge in edges:
        source, target = edge.get("source"), edge.get("target")
        command = f"kubectl exec -it warnet-tank-{source} -- bitcoin-cli addnode warnet-tank-{target}:18443 onetry"
        print(f"Connecting node {source} to node {target}")
        if run_command(command, stream_output=True):
            print(f"Successfully connected node {source} to node {target}")
        else:
            print(f"Failed to connect node {source} to node {target}")

    print("All connections attempted.")
