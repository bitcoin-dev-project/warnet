import json
import tempfile
from importlib.resources import files
from pathlib import Path
from typing import Any, Dict, List

import click
import networkx as nx
import yaml
from rich import print
from .bitcoin import _rpc
from .k8s import (
    apply_kubernetes_yaml,
    create_namespace,
    delete_namespace,
    deploy_base_configurations,
    run_command,
    stream_command,
    set_kubectl_context,
    create_kubernetes_object,
    get_edges,
    get_mission
)

DEFAULT_GRAPH_FILE = files("graphs").joinpath("default.graphml")
WAR_MANIFESTS = files("manifests")


@click.group(name="network")
def network():
    """Network commands"""


def read_graph_file(graph_file: Path) -> nx.Graph:
    with open(graph_file) as f:
        return nx.parse_graphml(f.read())


def generate_node_config(node: int, data: dict, graph: nx.Graph) -> str:
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

    # Add addnode configurations for connected nodes
    connected_nodes = list(graph.neighbors(node))
    addnode_configs = [f"addnode=warnet-tank-{index}-service" for index in connected_nodes]

    return f"{base_config}\n{node_specific_config}\n" + "\n".join(addnode_configs)


def create_node_deployment(node: int, data: dict) -> Dict[str, Any]:
    image = data.get("image", "bitcoindevproject/bitcoin:27.0")
    version = data.get("version", "27.0")

    return create_kubernetes_object(
        kind="Pod",
        metadata={
            "name": f"warnet-tank-{node}",
            "namespace": "warnet",
            "labels": {"app": "warnet", "mission": "tank", "index": str(node)},
            "annotations": {
                "data": json.dumps(data)
            }
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
                    "ports": [
                        {"containerPort": 18444},
                        {"containerPort": 18443},
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
            "selector": {"app": "warnet", "mission": "tank", "index": str(node)},
            "ports": [
                {"name": "p2p", "port": 18444, "targetPort": 18444},
                {"name": "rpc", "port": 18443, "targetPort": 18443},
            ],
        },
    )


def create_config_map(node: int, config: str) -> Dict[str, Any]:
    config_map = create_kubernetes_object(
        kind="ConfigMap",
        metadata={
            "name": f"bitcoin-config-tank-{node}",
            "namespace": "warnet",
        },
    )
    config_map["data"] = {"bitcoin.conf": config}
    return config_map


def create_edges_map(graph):
    edges = []
    for src, dst, data in graph.edges(data=True):
        edges.append({
            "src": src,
            "dst": dst,
            "data": data
        })
    config_map = create_kubernetes_object(
        kind="ConfigMap",
        metadata={
            "name": "edges",
            "namespace": "warnet",
        },
    )
    config_map["data"] = {"data": json.dumps(edges)}
    return config_map


def generate_kubernetes_yaml(graph: nx.Graph) -> List[Dict[str, Any]]:
    kubernetes_objects = [create_namespace()]

    for node, data in graph.nodes(data=True):
        config = generate_node_config(node, data, graph)
        kubernetes_objects.extend(
            [
                create_config_map(node, config),
                create_node_deployment(node, data),
                create_node_service(node),
            ]
        )
    kubernetes_objects.append(create_edges_map(graph))

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
        if not stream_command(command):
            print(f"Failed to run Helm command: {command}")
            return False
    return True


@network.command()
@click.argument("graph_file", default=DEFAULT_GRAPH_FILE, type=click.Path())
@click.option("--logging/--no-logging", default=False)
def start(graph_file: Path, logging: bool):
    """Start a warnet with topology loaded from a <graph_file>"""
    graph = read_graph_file(graph_file)
    kubernetes_yaml = generate_kubernetes_yaml(graph)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as temp_file:
        yaml.dump_all(kubernetes_yaml, temp_file)
        temp_file_path = temp_file.name

    try:
        if deploy_base_configurations() and apply_kubernetes_yaml(temp_file_path):
            print(f"Warnet network started successfully.")
            if not set_kubectl_context("warnet"):
                print(
                    "Warning: Failed to set kubectl context. You may need to manually switch to the warnet namespace."
                )
            if logging and not setup_logging_helm():
                print("Failed to install Helm charts.")
        else:
            print(f"Failed to start warnet network.")
    finally:
        Path(temp_file_path).unlink()


@network.command()
def down():
    """Bring down a running warnet"""
    if delete_namespace("warnet") and delete_namespace("warnet-logging"):
        print(f"Warnet network has been successfully brought down and the namespaces deleted.")
    else:
        print(f"Failed to bring down warnet network or delete the namespaces.")


@network.command()
@click.option("--follow", "-f", is_flag=True, help="Follow logs")
def logs(follow: bool):
    """Get Kubernetes logs from the RPC server"""
    command = f"kubectl logs rpc-0{' --follow' if follow else ''}"
    stream_command(command)


@network.command()
def connected():
    """Determine if all p2p conenctions defined in graph are established"""
    print(_connected())

def _connected():
    tanks = get_mission("tank")
    edges = get_edges()
    for tank in tanks:
        # Get actual
        index = tank.metadata.labels["index"]
        peerinfo = json.loads(_rpc(int(index), "getpeerinfo", ""))
        manuals = 0
        for peer in peerinfo:
            if peer["connection_type"] == "manual":
                manuals += 1
        # Get expected
        init_peers = sum(1 for edge in edges if edge["src"] == index)
        print(f"Tank {index} connections: expected={init_peers} actual={manuals}")
        # Even if more edges are specifed, bitcoind only allows
        # 8 manual outbound connections
        if min(8, init_peers) > manuals:
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
        status = {"tank_index": tank.metadata.labels["index"], "bitcoin_status": tank.status.phase.lower()}
        stats.append(status)
    return stats


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
