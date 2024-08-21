import os
import subprocess
from importlib.resources import files
import json
from typing import Any, Dict

from kubernetes import client, config
from kubernetes.dynamic import DynamicClient

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


def get_edges():
    sclient = get_static_client()
    configmap = sclient.read_namespaced_config_map(name="edges", namespace="warnet")
    return json.loads(configmap.data["data"])


def run_command(command) -> str:
    result = subprocess.run(
        command, shell=True, capture_output=True, text=True, executable="/bin/bash"
    )
    if result.returncode != 0:
        raise Exception(result.stderr)
    return result.stdout


def stream_command(command, env=None) -> bool:
    process = subprocess.Popen(
        ["/bin/bash", "-c", command],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True,
    )

    for line in iter(process.stdout.readline, ""):
        print(line, end="")

    process.stdout.close()
    return_code = process.wait()

    if return_code != 0:
        print(f"Command failed with return code {return_code}")
        return False
    return True


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
