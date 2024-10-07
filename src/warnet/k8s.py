import json
import os
import sys
import tempfile
from pathlib import Path
from time import sleep
from typing import Optional

import yaml
from kubernetes import client, config, watch
from kubernetes.client import CoreV1Api
from kubernetes.client.models import V1Namespace, V1Pod, V1PodList
from kubernetes.client.rest import ApiException
from kubernetes.dynamic import DynamicClient
from kubernetes.stream import stream

from .constants import (
    CADDY_INGRESS_NAME,
    DEFAULT_NAMESPACE,
    INGRESS_NAMESPACE,
    KUBE_INTERNAL_NAMESPACES,
    KUBECONFIG,
    LOGGING_NAMESPACE,
)
from .process import run_command, stream_command


class K8sError(Exception):
    pass


def get_static_client() -> CoreV1Api:
    config.load_kube_config(config_file=KUBECONFIG)
    return client.CoreV1Api()


def get_dynamic_client() -> DynamicClient:
    config.load_kube_config(config_file=KUBECONFIG)
    return DynamicClient(client.ApiClient())


def get_pods() -> list[V1Pod]:
    sclient = get_static_client()
    pods: list[V1Pod] = []
    namespaces = get_namespaces()
    for ns in namespaces:
        namespace = ns.metadata.name
        try:
            pod_list: V1PodList = sclient.list_namespaced_pod(namespace)
            for pod in pod_list.items:
                pods.append(pod)
        except Exception as e:
            raise e
    return pods


def get_pod(name: str, namespace: Optional[str] = None) -> V1Pod:
    namespace = get_default_namespace_or(namespace)
    sclient = get_static_client()
    return sclient.read_namespaced_pod(name=name, namespace=namespace)


def get_mission(mission: str) -> list[V1Pod]:
    pods = get_pods()
    crew: list[V1Pod] = []
    for pod in pods:
        if "mission" in pod.metadata.labels and pod.metadata.labels["mission"] == mission:
            crew.append(pod)
    return crew


def get_pod_exit_status(pod_name, namespace: Optional[str] = None):
    namespace = get_default_namespace_or(namespace)
    try:
        sclient = get_static_client()
        pod = sclient.read_namespaced_pod(name=pod_name, namespace=namespace)
        for container_status in pod.status.container_statuses:
            if container_status.state.terminated:
                return container_status.state.terminated.exit_code
        return None
    except client.ApiException as e:
        print(f"Exception when calling CoreV1Api->read_namespaced_pod: {e}")
        return None


def get_edges(namespace: Optional[str] = None) -> any:
    namespace = get_default_namespace_or(namespace)
    sclient = get_static_client()
    configmap = sclient.read_namespaced_config_map(name="edges", namespace=namespace)
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
    return run_command(command)


def delete_pod(pod_name: str, namespace: Optional[str] = None) -> bool:
    namespace = get_default_namespace_or(namespace)
    command = f"kubectl -n {namespace} delete pod {pod_name}"
    return stream_command(command)


def get_default_namespace() -> str:
    command = "kubectl config view --minify -o jsonpath='{..namespace}'"
    try:
        kubectl_namespace = run_command(command)
    except Exception as e:
        print(e)
        if str(e).find("command not found"):
            print(
                "It looks like kubectl is not installed. Please install it to continue: "
                "https://kubernetes.io/docs/tasks/tools/"
            )
        sys.exit(1)
    return kubectl_namespace if kubectl_namespace else DEFAULT_NAMESPACE


def get_default_namespace_or(namespace: Optional[str]) -> str:
    return namespace if namespace else get_default_namespace()


def snapshot_bitcoin_datadir(
    pod_name: str,
    chain: str,
    local_path: str = "./",
    filters: list[str] = None,
    namespace: Optional[str] = None,
) -> None:
    namespace = get_default_namespace_or(namespace)
    sclient = get_static_client()

    try:
        sclient.read_namespaced_pod(name=pod_name, namespace=namespace)

        # Filter down to the specified list of directories and files
        # This allows for creating snapshots of only the relevant data, e.g.,
        # we may want to snapshot the blocks but not snapshot peers.dat or the node
        # wallets.
        #
        # TODO: never snapshot bitcoin.conf, as this is managed by the helm config
        if filters:
            find_command = [
                "find",
                f"/root/.bitcoin/{chain}",
                "(",
                "-type",
                "f",
                "-o",
                "-type",
                "d",
                ")",
                "(",
                "-name",
                filters[0],
            ]
            for f in filters[1:]:
                find_command.extend(["-o", "-name", f])
            find_command.append(")")
        else:
            # If no filters, get everything in the Bitcoin directory (TODO: exclude bitcoin.conf)
            find_command = ["find", f"/root/.bitcoin/{chain}"]

        resp = stream(
            sclient.connect_get_namespaced_pod_exec,
            pod_name,
            namespace,
            command=find_command,
            stderr=True,
            stdin=False,
            stdout=True,
            tty=False,
            _preload_content=False,
        )

        file_list = []
        while resp.is_open():
            resp.update(timeout=1)
            if resp.peek_stdout():
                file_list.extend(resp.read_stdout().strip().split("\n"))
            if resp.peek_stderr():
                print(f"Error: {resp.read_stderr()}")

        resp.close()
        if not file_list:
            print("No matching files or directories found.")
            return
        tar_command = ["tar", "-czf", "/tmp/bitcoin_data.tar.gz", "-C", f"/root/.bitcoin/{chain}"]
        tar_command.extend(
            [os.path.relpath(f, f"/root/.bitcoin/{chain}") for f in file_list if f.strip()]
        )
        resp = stream(
            sclient.connect_get_namespaced_pod_exec,
            pod_name,
            namespace,
            command=tar_command,
            stderr=True,
            stdin=False,
            stdout=True,
            tty=False,
            _preload_content=False,
        )
        while resp.is_open():
            resp.update(timeout=1)
            if resp.peek_stdout():
                print(f"Tar output: {resp.read_stdout()}")
            if resp.peek_stderr():
                print(f"Error: {resp.read_stderr()}")
        resp.close()
        local_file_path = Path(local_path) / f"{pod_name}_bitcoin_data.tar.gz"
        copy_command = (
            f"kubectl cp {namespace}/{pod_name}:/tmp/bitcoin_data.tar.gz {local_file_path}"
        )
        if not stream_command(copy_command):
            raise Exception("Failed to copy tar file from pod to local machine")

        print(f"Bitcoin data exported successfully to {local_file_path}")
        cleanup_command = ["rm", "/tmp/bitcoin_data.tar.gz"]
        stream(
            sclient.connect_get_namespaced_pod_exec,
            pod_name,
            namespace,
            command=cleanup_command,
            stderr=True,
            stdin=False,
            stdout=True,
            tty=False,
        )

        print("To untar and repopulate the directory, use the following command:")
        print(f"tar -xzf {local_file_path} -C /path/to/destination/.bitcoin/{chain}")

    except Exception as e:
        print(f"An error occurred: {str(e)}")


def wait_for_pod_ready(name, namespace, timeout=300):
    sclient = get_static_client()
    w = watch.Watch()
    for event in w.stream(
        sclient.list_namespaced_pod, namespace=namespace, timeout_seconds=timeout
    ):
        pod = event["object"]
        if pod.metadata.name == name and pod.status.phase == "Running":
            conditions = pod.status.conditions or []
            ready_condition = next((c for c in conditions if c.type == "Ready"), None)
            if ready_condition and ready_condition.status == "True":
                w.stop()
                return True
    print(f"Timeout waiting for pod {name} to be ready.")
    return False


def wait_for_init(pod_name, timeout=300, namespace: Optional[str] = None):
    namespace = get_default_namespace_or(namespace)
    sclient = get_static_client()
    w = watch.Watch()
    for event in w.stream(
        sclient.list_namespaced_pod, namespace=namespace, timeout_seconds=timeout
    ):
        pod = event["object"]
        if pod.metadata.name == pod_name:
            if not pod.status.init_container_statuses:
                continue
            for init_container_status in pod.status.init_container_statuses:
                if init_container_status.state.running:
                    print(f"initContainer in pod {pod_name} ({namespace}) is ready")
                    w.stop()
                    return True
    print(f"Timeout waiting for initContainer in {pod_name} ({namespace})to be ready.")
    return False


def wait_for_ingress_controller(timeout=300):
    # get name of ingress controller pod
    sclient = get_static_client()
    pods = sclient.list_namespaced_pod(namespace=INGRESS_NAMESPACE)
    for pod in pods.items:
        if "ingress-nginx-controller" in pod.metadata.name:
            return wait_for_pod_ready(pod.metadata.name, INGRESS_NAMESPACE, timeout)


def get_ingress_ip_or_host():
    config.load_kube_config()
    networking_v1 = client.NetworkingV1Api()
    try:
        ingress = networking_v1.read_namespaced_ingress(CADDY_INGRESS_NAME, LOGGING_NAMESPACE)
        if ingress.status.load_balancer.ingress[0].hostname:
            return ingress.status.load_balancer.ingress[0].hostname
        return ingress.status.load_balancer.ingress[0].ip
    except Exception as e:
        print(f"Error getting ingress IP: {e}")
        return None


def pod_log(pod_name, container_name=None, follow=False, namespace: Optional[str] = None):
    namespace = get_default_namespace_or(namespace)
    sclient = get_static_client()

    try:
        return sclient.read_namespaced_pod_log(
            name=pod_name,
            namespace=namespace,
            container=container_name,
            follow=follow,
            _preload_content=False,
        )
    except ApiException as e:
        raise Exception(json.loads(e.body.decode("utf-8"))["message"]) from None


def wait_for_pod(pod_name, timeout_seconds=10, namespace: Optional[str] = None):
    namespace = get_default_namespace_or(namespace)
    sclient = get_static_client()
    while timeout_seconds > 0:
        pod = sclient.read_namespaced_pod_status(name=pod_name, namespace=namespace)
        if pod.status.phase != "Pending":
            return
        sleep(1)
        timeout_seconds -= 1


def write_file_to_container(
    pod_name, container_name, dst_path, data, namespace: Optional[str] = None
):
    namespace = get_default_namespace_or(namespace)
    sclient = get_static_client()
    exec_command = ["sh", "-c", f"cat > {dst_path}.tmp && sync"]
    try:
        res = stream(
            sclient.connect_get_namespaced_pod_exec,
            pod_name,
            namespace,
            command=exec_command,
            container=container_name,
            stdin=True,
            stderr=True,
            stdout=True,
            tty=False,
            _preload_content=False,
        )
        res.write_stdin(data)
        res.close()
        rename_command = ["sh", "-c", f"mv {dst_path}.tmp {dst_path}"]
        stream(
            sclient.connect_get_namespaced_pod_exec,
            pod_name,
            namespace,
            command=rename_command,
            container=container_name,
            stdin=False,
            stderr=True,
            stdout=True,
            tty=False,
        )
        print(f"Successfully copied data to {pod_name}({container_name}):{dst_path}")
        return True
    except Exception as e:
        print(f"Failed to copy data to {pod_name}({container_name}):{dst_path}:\n{e}")


def get_kubeconfig_value(jsonpath):
    command = f"kubectl config view --minify --raw -o jsonpath={jsonpath}"
    return run_command(command)


def get_cluster_of_current_context(kubeconfig_data: dict) -> dict:
    # Get the current context name
    current_context_name = kubeconfig_data.get("current-context")

    if not current_context_name:
        raise K8sError("No current context found in kubeconfig.")

    # Find the context entry for the current context
    context_entry = next(
        (
            context
            for context in kubeconfig_data.get("contexts", [])
            if context["name"] == current_context_name
        ),
        None,
    )

    if not context_entry:
        raise K8sError(f"Context '{current_context_name}' not found in kubeconfig.")

    # Get the cluster name from the context entry
    cluster_name = context_entry.get("context", {}).get("cluster")

    if not cluster_name:
        raise K8sError(f"Cluster not specified in context '{current_context_name}'.")

    # Find the cluster entry associated with the cluster name
    cluster_entry = next(
        (
            cluster
            for cluster in kubeconfig_data.get("clusters", [])
            if cluster["name"] == cluster_name
        ),
        None,
    )

    if not cluster_entry:
        raise K8sError(f"Cluster '{cluster_name}' not found in kubeconfig.")

    return cluster_entry


def get_namespaces() -> list[V1Namespace]:
    sclient = get_static_client()
    try:
        return [
            ns
            for ns in sclient.list_namespace().items
            if ns.metadata.name not in KUBE_INTERNAL_NAMESPACES
        ]

    except ApiException as e:
        if e.status == 403:
            ns = sclient.read_namespace(name=get_default_namespace())
            return [ns]
        else:
            return []


def get_namespaces_by_type(namespace_type: str) -> list[V1Namespace]:
    """
    Get all namespaces beginning with `prefix`. Returns empty list of no namespaces with the specified prefix are found.
    """
    namespaces = get_namespaces()
    return [ns for ns in namespaces if ns.metadata.name.startswith(namespace_type)]


def get_service_accounts_in_namespace(namespace):
    """
    Get all service accounts in a namespace. Returns an empty list if no service accounts are found in the specified namespace.
    """
    command = f"kubectl get serviceaccounts -n {namespace} -o jsonpath={{.items[*].metadata.name}}"
    # skip the default service account created by k8s
    service_accounts = run_command(command).split()
    return [sa for sa in service_accounts if sa != "default"]


def can_delete_pods(namespace: Optional[str] = None) -> bool:
    namespace = get_default_namespace_or(namespace)

    get_static_client()
    auth_api = client.AuthorizationV1Api()

    # Define the SelfSubjectAccessReview request for deleting pods
    access_review = client.V1SelfSubjectAccessReview(
        spec=client.V1SelfSubjectAccessReviewSpec(
            resource_attributes=client.V1ResourceAttributes(
                namespace=namespace,
                verb="delete",  # Action: 'delete'
                resource="pods",  # Resource: 'pods'
            )
        )
    )

    try:
        # Perform the SelfSubjectAccessReview check
        review_response = auth_api.create_self_subject_access_review(body=access_review)

        # Check the result and return
        if review_response.status.allowed:
            print(f"Service account can delete pods in namespace '{namespace}'.")
            return True
        else:
            print(f"Service account CANNOT delete pods in namespace '{namespace}'.")
            return False

    except ApiException as e:
        print(f"An error occurred: {e}")
        return False


def open_kubeconfig(kubeconfig_path: str) -> dict:
    try:
        with open(kubeconfig_path) as file:
            return yaml.safe_load(file)
    except FileNotFoundError as e:
        raise K8sError(f"Kubeconfig file {kubeconfig_path} not found.") from e
    except yaml.YAMLError as e:
        raise K8sError(f"Error parsing kubeconfig: {e}") from e


def write_kubeconfig(kube_config: dict, kubeconfig_path: str) -> None:
    dir_name = os.path.dirname(kubeconfig_path)
    try:
        with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False) as temp_file:
            yaml.safe_dump(kube_config, temp_file)
        os.replace(temp_file.name, kubeconfig_path)
    except Exception as e:
        os.remove(temp_file.name)
        raise K8sError(f"Error writing kubeconfig: {kubeconfig_path}") from e
