import json
import tempfile
from pathlib import Path

import yaml
from kubernetes import client, config
from kubernetes.client.models import (
    CoreV1Event,
    V1DeploymentList,
    V1PodList,
    V1ServiceList,
    V1Status,
)
from kubernetes.client.rest import ApiException
from kubernetes.dynamic import DynamicClient
from rich.console import Console

from .process import run_command, stream_command

DEFAULT_NAMESPACE = "warnet"


def get_static_client() -> CoreV1Event:
    config.load_kube_config()
    return client.CoreV1Api()


def get_apps_client() -> CoreV1Event:
    config.load_kube_config()
    return client.AppsV1Api()


def get_dynamic_client() -> DynamicClient:
    config.load_kube_config()
    return DynamicClient(client.ApiClient())


def get_pods() -> V1PodList:
    sclient = get_static_client()
    try:
        pod_list: V1PodList = sclient.list_namespaced_pod(get_default_namespace())
    except Exception as e:
        raise e
    return pod_list


def get_services() -> V1ServiceList:
    sclient = get_static_client()
    try:
        service_list: V1ServiceList = sclient.list_namespaced_service(get_default_namespace())
    except Exception as e:
        raise e
    return service_list


def get_deployments() -> V1DeploymentList:
    sclient = get_apps_client()
    try:
        deployment_list: V1DeploymentList = sclient.list_namespaced_deployment(
            get_default_namespace()
        )
    except Exception as e:
        raise e
    return deployment_list


def delete_pod(pod_name: str) -> V1Status:
    sclient = get_static_client()
    try:
        status: V1Status = sclient.delete_namespaced_pod(pod_name, get_default_namespace())
    except Exception as e:
        raise e
    return status


def delete_service(service_name: str) -> V1Status:
    sclient = get_static_client()
    try:
        status: V1Status = sclient.delete_namespaced_service(service_name, get_default_namespace())
    except Exception as e:
        raise e
    return status


def delete_deployment(deployment_name: str) -> V1Status:
    sclient = get_apps_client()
    try:
        status: V1Status = sclient.delete_namespaced_deployment(
            deployment_name, get_default_namespace()
        )
    except Exception as e:
        raise e
    return status


def delete_all_resources():
    namespace = get_default_namespace()
    console = Console()

    # Delete all deployments
    deployments = get_deployments()
    with console.status("[yellow]Cleaning up deployments...[/yellow]"):
        aclient = get_apps_client()
        for deployment in deployments.items:
            aclient.delete_namespaced_deployment(deployment.metadata.name, namespace)
            console.print(f"[green]deleted deployment: {deployment.metadata.name}[/green]")

    # Delete all services
    services = get_services()
    with console.status("[yellow]Cleaning up services...[/yellow]"):
        sclient = get_static_client()
        for service in services.items:
            sclient.delete_namespaced_service(service.metadata.name, namespace)
            console.print(f"[green]deleted service: {service.metadata.name}[/green]")

    # Delete any remaining pods
    pods = get_pods()
    with console.status("[yellow]Cleaning up remaining pods...[/yellow]"):
        for pod in pods.items:
            sclient.delete_namespaced_pod(pod.metadata.name, namespace)
            console.print(f"[green]deleted pod: {pod.metadata.name}[/green]")


def get_mission(mission: str) -> list[V1PodList]:
    pods = get_pods()
    crew = []
    for pod in pods.items:
        if "mission" in pod.metadata.labels and pod.metadata.labels["mission"] == mission:
            crew.append(pod)
    return crew


def get_pod_exit_status(pod_name):
    try:
        sclient = get_static_client()
        pod = sclient.read_namespaced_pod(name=pod_name, namespace=get_default_namespace())
        for container_status in pod.status.container_statuses:
            if container_status.state.terminated:
                return container_status.state.terminated.exit_code
        return None
    except client.ApiException as e:
        print(f"Exception when calling CoreV1Api->read_namespaced_pod: {e}")
        return None


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
    try:
        sclient = get_static_client()
        sclient.delete_namespace(name=namespace)
        print(f"Namespace {namespace} deleted successfully")
        return True
    except ApiException as e:
        if e.status == 404:
            print(f"Namespace {namespace} not found")
            return True  # Mimic the behavior of --ignore-not-found
        else:
            print(f"Exception when calling CoreV1Api->delete_namespace: {e}")
            return False


def get_default_namespace() -> str:
    command = "kubectl config view --minify -o jsonpath='{..namespace}'"
    kubectl_namespace = run_command(command)
    return kubectl_namespace if kubectl_namespace else DEFAULT_NAMESPACE
