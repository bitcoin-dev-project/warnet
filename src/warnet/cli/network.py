import json
import tempfile
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
@click.option("--force", default=False, is_flag=True, type=bool)
@click.option("--network", default="warnet", show_default=True)
def start(graph_file: Path, force: bool, network: str):
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
    bitcoin_config = data.get("bitcoin_config", "")

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
                        {"name": "BITCOIN_CONFIG", "value": bitcoin_config},
                    ],
                }
            ]
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
