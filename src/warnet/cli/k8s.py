import json
import tempfile
from importlib.resources import files
from pathlib import Path

import yaml
from kubernetes import client, config
from kubernetes.client.models import CoreV1Event, V1PodList
from kubernetes.dynamic import DynamicClient

from .process import run_command, stream_command

WAR_MANIFESTS = files("manifests")
DEFAULT_NAMESPACE = "warnet"


def get_static_client() -> CoreV1Event:
    config.load_kube_config()
    return client.CoreV1Api()


def get_dynamic_client() -> DynamicClient:
    config.load_kube_config()
    return DynamicClient(client.ApiClient())


def get_pods() -> V1PodList:
    sclient = get_static_client()
    return sclient.list_namespaced_pod("warnet")


def get_mission(mission: str) -> list[V1PodList]:
    pods = get_pods()
    crew = []
    for pod in pods.items:
        if "mission" in pod.metadata.labels and pod.metadata.labels["mission"] == mission:
            crew.append(pod)
    return crew


def get_edges() -> any:
    sclient = get_static_client()
    configmap = sclient.read_namespaced_config_map(name="edges", namespace="warnet")
    return json.loads(configmap.data["data"])


def create_kubernetes_object(
    kind: str, metadata: dict[str, any], spec: dict[str, any] = None
) -> dict[str, any]:
    metadata["namespace"] = get_default_namespace()
    obj = {
        "apiVersion": "v1",
        "kind": kind,
        "metadata": metadata,
    }
    if spec is not None:
        obj["spec"] = spec
    return obj


def set_kubectl_context(namespace: str) -> bool:
    """
    Set the default kubectl context to the specified namespace.
    """
    command = f"kubectl config set-context --current --namespace={namespace}"
    result = stream_command(command)
    if result:
        print(f"Kubectl context set to namespace: {namespace}")
    else:
        print(f"Failed to set kubectl context to namespace: {namespace}")
    return result


def apply_kubernetes_yaml(yaml_file: str) -> bool:
    command = f"kubectl apply -f {yaml_file}"
    return stream_command(command)


def apply_kubernetes_yaml_obj(yaml_obj: str) -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as temp_file:
        yaml.dump(yaml_obj, temp_file)
        temp_file_path = temp_file.name

    try:
        apply_kubernetes_yaml(temp_file_path)
    finally:
        Path(temp_file_path).unlink()


def delete_namespace(namespace: str) -> bool:
    command = f"kubectl delete namespace {namespace} --ignore-not-found"
    return stream_command(command)


def delete_pod(pod_name: str) -> bool:
    command = f"kubectl delete pod {pod_name}"
    return stream_command(command)


def get_default_namespace() -> str:
    command = "kubectl config view --minify -o jsonpath='{..namespace}'"
    kubectl_namespace = run_command(command)
    return kubectl_namespace if kubectl_namespace else DEFAULT_NAMESPACE
