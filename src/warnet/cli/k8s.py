from importlib.resources import files

from kubernetes import client, config
from kubernetes.dynamic import DynamicClient

from .process import run_command

WAR_MANIFESTS = files("manifests")


def get_static_client():
    config.load_kube_config()
    return client.CoreV1Api()


def get_dynamic_client():
    config.load_kube_config()
    return DynamicClient(client.ApiClient())


def get_pods():
    sclient = get_static_client()
    return sclient.list_namespaced_pod("warnet")


def get_mission(mission):
    pods = get_pods()
    crew = []
    for pod in pods.items:
        if "mission" in pod.metadata.labels and pod.metadata.labels["mission"] == mission:
            crew.append(pod)
    return crew


def create_namespace() -> dict:
    return {"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": "warnet"}}


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


def deploy_base_configurations():
    base_configs = [
        "namespace.yaml",
        "rbac-config.yaml",
    ]

    for bconfig in base_configs:
        command = f"kubectl apply -f {WAR_MANIFESTS}/{bconfig}"
        if not run_command(command, stream_output=True):
            print(f"Failed to apply {bconfig}")
            return False
    return True


def apply_kubernetes_yaml(yaml_file: str):
    command = f"kubectl apply -f {yaml_file}"
    return run_command(command, stream_output=True)


def delete_namespace(namespace: str):
    command = f"kubectl delete namespace {namespace}"
    return run_command(command, stream_output=True)
