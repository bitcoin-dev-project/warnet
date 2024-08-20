import tempfile
import xml.etree.ElementTree as ET
from importlib.resources import files
from pathlib import Path

import click
import networkx as nx
import yaml
from rich import print

from .util import run_command

DEFAULT_GRAPH_FILE = files("graphs").joinpath("default.graphml")
WAR_MANIFESTS = files("manifests")


@click.group(name="network")
def network():
    """Network commands"""


def set_kubectl_context(namespace: str):
    """
    Set the default kubectl context to the specified namespace.
    """
    command = f"kubectl config set-context --current --namespace={namespace}"
    result = run_command(command, stream_output=True)
    if result:
        print(f"Kubectl context set to namespace: {namespace}")
    else:
        print(f"Failed to set kubectl context to namespace: {namespace}")
    return result


@network.command()
@click.argument("graph_file", default=DEFAULT_GRAPH_FILE, type=click.Path())
@click.option("--network", default="warnet", show_default=True)
@click.option("--logging/--no-logging", default=False)
def start(graph_file: Path, logging: bool, network: str):
    """
    Start a warnet with topology loaded from a <graph_file> into [network]
    """
    # Generate the Kubernetes YAML
    graph = read_graph_file(graph_file)
    kubernetes_yaml = generate_kubernetes_yaml(graph)

    # Write the YAML to a temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as temp_file:
        yaml.dump_all(kubernetes_yaml, temp_file)
        temp_file_path = temp_file.name

    try:
        # Deploy base configurations
        base_configs = [
            "namespace.yaml",
            "rbac-config.yaml",
        ]

        for config in base_configs:
            command = f"kubectl apply -f {WAR_MANIFESTS}/{config}"
            result = run_command(command, stream_output=True)
            if not result:
                print(f"Failed to apply {config}")
                return

        # Apply the YAML using kubectl
        command = f"kubectl apply -f {temp_file_path}"
        result = run_command(command, stream_output=True)

        if result:
            print(f"Warnet '{network}' started successfully.")

            # Set kubectl context to the warnet namespace
            context_result = set_kubectl_context(network)
            if not context_result:
                print(
                    "Warning: Failed to set kubectl context. You may need to manually switch to the warnet namespace."
                )

            if logging:
                helm_result = setup_logging_helm()
                if helm_result:
                    print("Helm charts installed successfully.")
                else:
                    print("Failed to install Helm charts.")
        else:
            print(f"Failed to start warnet '{network}'.")
    finally:
        # Clean up the temporary file
        Path(temp_file_path).unlink()


@network.command()
@click.option("--network", default="warnet", show_default=True)
def down(network: str):
    """
    Bring down a running warnet named [network]
    """
    # Delete the namespace
    command = f"kubectl delete namespace {network}"
    result = run_command(command, stream_output=True)
    # TODO: Fix this
    command = "kubectl delete namespace warnet-logging"
    result = run_command(command, stream_output=True)

    if result:
        print(f"Warnet '{network}' has been successfully brought down and the namespace deleted.")
    else:
        print(f"Failed to bring down warnet '{network}' or delete the namespace.")


@network.command()
@click.option("--follow", "-f", is_flag=True, help="Follow logs")
def logs(follow: bool):
    """Get Kubernetes logs from the RPC server"""
    command = "kubectl logs rpc-0"
    stream_output = False
    if follow:
        command += " --follow"
        stream_output = True

    run_command(command, stream_output=stream_output)


@network.command()
@click.argument("graph_file", default=DEFAULT_GRAPH_FILE, type=click.Path())
@click.option("--output", "-o", default="warnet-deployment.yaml", help="Output YAML file")
def generate_yaml(graph_file: Path, output: str):
    """
    Generate a Kubernetes YAML file from a graph file for deploying warnet nodes.
    """
    # Read and parse the graph file
    graph = read_graph_file(graph_file)

    # Generate the Kubernetes YAML
    kubernetes_yaml = generate_kubernetes_yaml(graph)

    # Write the YAML to a file
    with open(output, "w") as f:
        yaml.dump_all(kubernetes_yaml, f)

    print(f"Kubernetes YAML file generated: {output}")


def read_graph_file(graph_file: Path) -> nx.Graph:
    with open(graph_file) as f:
        return nx.parse_graphml(f.read())


def generate_kubernetes_yaml(graph: nx.Graph) -> list:
    kubernetes_objects = []

    # Add Namespace object
    namespace = create_namespace()
    kubernetes_objects.append(namespace)

    for node, data in graph.nodes(data=True):
        # Create a ConfigMap for each node
        config = generate_node_config(node, data)
        config_map = create_config_map(node, config)
        kubernetes_objects.append(config_map)

        # Create a deployment for each node
        deployment = create_node_deployment(node, data)
        kubernetes_objects.append(deployment)

        # Create a service for each node
        service = create_node_service(node)
        kubernetes_objects.append(service)

    return kubernetes_objects


def create_namespace() -> dict:
    return {"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": "warnet"}}


def create_node_deployment(node: int, data: dict) -> dict:
    image = data.get("image", "bitcoindevproject/bitcoin:27.0")
    version = data.get("version", "27.0")

    return {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": f"warnet-node-{node}",
            "namespace": "warnet",
            "labels": {"app": "warnet", "node": str(node)},
        },
        "spec": {
            "containers": [
                {
                    "name": "bitcoin",
                    "image": image,
                    "env": [
                        {"name": "BITCOIN_VERSION", "value": version},
                    ],
                    "volumeMounts": [
                        {
                            "name": "config",
                            "mountPath": "/root/.bitcoin/bitcoin.conf",
                            "subPath": "bitcoin.conf",
                        }
                    ],
                }
            ],
            "volumes": [{"name": "config", "configMap": {"name": f"bitcoin-config-node-{node}"}}],
        },
    }


def create_node_service(node: int) -> dict:
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {"name": f"warnet-node-{node}-service", "namespace": "warnet"},
        "spec": {
            "selector": {"app": "warnet", "node": str(node)},
            "ports": [{"port": 8333, "targetPort": 8333}],
        },
    }


def setup_logging_helm():
    """
    Run the required Helm commands for setting up Grafana, Prometheus, and Loki.
    """
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
        result = run_command(command, stream_output=True)
        if not result:
            print(f"Failed to run Helm command: {command}")
            return False
    return True


@network.command()
@click.argument("graph_file", default=DEFAULT_GRAPH_FILE, type=click.Path(exists=True))
def connect(graph_file: Path):
    """
    Connect nodes based on the edges defined in the graph file.
    """
    # Parse the GraphML file
    tree = ET.parse(graph_file)
    root = tree.getroot()

    # Find all edge elements
    edges = root.findall(".//{http://graphml.graphdrawing.org/xmlns}edge")

    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")

        # Construct the kubectl command
        command = f"kubectl exec -it warnet-node-{source} -- bitcoin-cli -rpcuser=user -rpcpassword=password addnode warnet-node-{target}-service:8333 add"

        print(f"Connecting node {source} to node {target}")
        result = run_command(command, stream_output=True)

        if result:
            print(f"Successfully connected node {source} to node {target}")
        else:
            print(f"Failed to connect node {source} to node {target}")

    print("All connections attempted.")


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
    node_specific_config = data.get("bitcoin_config", "")
    return f"{base_config}\n{node_specific_config.replace(",", "\n")}"


def create_config_map(node: int, config: str) -> dict:
    return {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {
            "name": f"bitcoin-config-node-{node}",
            "namespace": "warnet",
        },
        "data": {"bitcoin.conf": config},
    }
