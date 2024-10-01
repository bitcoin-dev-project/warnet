import json
import os
import sys
import tempfile
from pathlib import Path
from time import sleep
from typing import Optional

import yaml
from kubernetes import client, config, watch
from kubernetes.client.models import CoreV1Event, V1Pod, V1PodList
from kubernetes.client.rest import ApiException
from kubernetes.dynamic import DynamicClient
from kubernetes.stream import stream

from .constants import (
    CADDY_INGRESS_NAME,
    DEFAULT_NAMESPACE,
    INGRESS_NAMESPACE,
    KUBECONFIG,
    LOGGING_NAMESPACE,
)
from .process import run_command, stream_command


def get_static_client() -> CoreV1Event:
    config.load_kube_config(config_file=KUBECONFIG)
    return client.CoreV1Api()


def get_dynamic_client() -> DynamicClient:
    config.load_kube_config(config_file=KUBECONFIG)
    return DynamicClient(client.ApiClient())


def get_pods() -> V1PodList:
    sclient = get_static_client()
    try:
        pod_list: V1PodList = sclient.list_namespaced_pod(get_default_namespace())
    except Exception as e:
        raise e
    return pod_list


def get_pod(name: str, namespace: Optional[str] = None) -> V1Pod:
    sclient = get_static_client()
    if not namespace:
        namespace = get_default_namespace()
    return sclient.read_namespaced_pod(name=name, namespace=namespace)


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
    command = f"kubectl delete namespace {namespace} --ignore-not-found"
    return run_command(command)


def delete_pod(pod_name: str) -> bool:
    command = f"kubectl -n {get_default_namespace()} delete pod {pod_name}"
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


def snapshot_bitcoin_datadir(
    pod_name: str, chain: str, local_path: str = "./", filters: list[str] = None
) -> None:
    namespace = get_default_namespace()
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


def wait_for_init(pod_name, timeout=300):
    sclient = get_static_client()
    namespace = get_default_namespace()
    w = watch.Watch()
    for event in w.stream(
        sclient.list_namespaced_pod, namespace=namespace, timeout_seconds=timeout
    ):
        pod = event["object"]
        if pod.metadata.name == pod_name:
            for init_container_status in pod.status.init_container_statuses:
                if init_container_status.state.running:
                    print(f"initContainer in pod {pod_name} is ready")
                    w.stop()
                    return True
    print(f"Timeout waiting for initContainer in {pod_name} to be ready.")
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


def pod_log(pod_name, container_name=None, follow=False):
    sclient = get_static_client()
    try:
        return sclient.read_namespaced_pod_log(
            name=pod_name,
            namespace=get_default_namespace(),
            container=container_name,
            follow=follow,
            _preload_content=False,
        )
    except ApiException as e:
        raise Exception(json.loads(e.body.decode("utf-8"))["message"]) from None


def wait_for_pod(pod_name, timeout_seconds=10):
    sclient = get_static_client()
    while timeout_seconds > 0:
        pod = sclient.read_namespaced_pod_status(name=pod_name, namespace=get_default_namespace())
        if pod.status.phase != "Pending":
            return
        sleep(1)
        timeout_seconds -= 1


def write_file_to_container(pod_name, container_name, dst_path, data):
    sclient = get_static_client()
    namespace = get_default_namespace()
    exec_command = ["sh", "-c", f"cat > {dst_path}"]
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
        print(f"Successfully copied data to {pod_name}({container_name}):{dst_path}")
        return True
    except Exception as e:
        print(f"Failed to copy data to {pod_name}({container_name}):{dst_path}:\n{e}")
