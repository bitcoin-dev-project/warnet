import json
import os
import tempfile
from pathlib import Path
from time import sleep
from typing import Optional

import yaml
from kubernetes import client, config, watch
from kubernetes.client.api import CoreV1Api
from kubernetes.client.models import V1DeleteOptions, V1Pod, V1PodList, V1Service, V1Status
from kubernetes.client.rest import ApiException
from kubernetes.dynamic import DynamicClient
from kubernetes.stream import stream
from kubernetes.utils import create_from_yaml
from urllib3 import HTTPResponse

from .constants import (
    CADDY_INGRESS_NAME,
    INGRESS_NAMESPACE,
    KUBECONFIG,
    LOGGING_NAMESPACE,
)


class K8sError(Exception):
    pass


def get_static_client() -> CoreV1Api:
    config.load_kube_config(config_file=KUBECONFIG)
    return client.CoreV1Api()


def get_dynamic_client() -> DynamicClient:
    config.load_kube_config(config_file=KUBECONFIG)
    return DynamicClient(client.ApiClient())


def kexec(pod: str, namespace: str, cmd: [str]) -> str:
    """It's `kubectl exec` but with a k at the beginning so as not to conflict with python's `exec`"""
    sclient = get_static_client()
    resp = stream(
        sclient.connect_get_namespaced_pod_exec,
        pod,
        namespace,
        command=cmd,
        stderr=True,
        stdin=False,
        stdout=True,
        tty=False,
    )
    return resp


def get_service(name: str, namespace: Optional[str] = None) -> V1Service:
    sclient = get_static_client()
    if not namespace:
        namespace = get_default_namespace()
    return sclient.read_namespaced_service(name=name, namespace=namespace)


def get_pod(name: str, namespace: Optional[str] = None) -> V1Pod:
    sclient = get_static_client()
    if not namespace:
        namespace = get_default_namespace()
    return sclient.read_namespaced_pod(name=name, namespace=namespace)


def get_pods() -> V1PodList:
    sclient = get_static_client()
    try:
        pod_list: V1PodList = sclient.list_namespaced_pod(get_default_namespace())
    except Exception as e:
        raise e
    return pod_list


def get_mission(mission: str) -> list[V1Pod]:
    pods = get_pods()
    crew = []
    for pod in pods.items:
        if "mission" in pod.metadata.labels and pod.metadata.labels["mission"] == mission:
            crew.append(pod)
    return crew


def get_pod_exit_status(pod_name):
    try:
        pod = get_pod(pod_name)
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
    kind: str, metadata: dict[str, any], spec: Optional[dict[str, any]] = None
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


def get_context_entry(kubeconfig_data: dict) -> dict:
    current_context_name = kubeconfig_data.get("current-context")
    if not current_context_name:
        raise K8sError(f"Could not determine current context from config data: {kubeconfig_data}")

    context_entry = next(
        (
            ctx
            for ctx in kubeconfig_data.get("contexts", [])
            if ctx.get("name") == current_context_name
        ),
        None,
    )

    if not context_entry:
        raise K8sError(f"Context '{current_context_name}' not found in kubeconfig.")

    return context_entry


def set_context_namespace(namespace: str) -> None:
    """
    Set the namespace within the KUBECONFIG's current context
    """
    try:
        kubeconfig_data = open_kubeconfig()
    except K8sError as e:
        raise K8sError(f"Could not open KUBECONFIG: {KUBECONFIG}") from e

    try:
        context_entry = get_context_entry(kubeconfig_data)
    except K8sError as e:
        raise K8sError(f"Could not get context entry for {KUBECONFIG}") from e

    context_entry["context"]["namespace"] = namespace

    try:
        write_kubeconfig(kubeconfig_data)
    except Exception as e:
        raise K8sError(f"Could not write to KUBECONFIG: {KUBECONFIG}") from e


def get_default_namespace() -> str:
    try:
        kubeconfig_data = open_kubeconfig()
    except K8sError as e:
        raise K8sError(f"Could not open KUBECONFIG: {KUBECONFIG}") from e

    try:
        context_entry = get_context_entry(kubeconfig_data)
    except K8sError as e:
        raise K8sError(f"Could not get context entry for {KUBECONFIG}") from e

    # TODO: need to settle on Warnet's "default" namespace
    namespace = context_entry["context"].get("namespace", "warnet")

    return namespace


def apply_kubernetes_yaml(yaml_file: str) -> bool:
    v1 = get_static_client()
    path = os.path.abspath(yaml_file)
    try:
        create_from_yaml(v1, path)
        return True
    except Exception as e:
        raise e


def apply_kubernetes_yaml_obj(yaml_obj: str) -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as temp_file:
        yaml.dump(yaml_obj, temp_file)
        temp_file_path = temp_file.name

    try:
        apply_kubernetes_yaml(temp_file_path)
    finally:
        Path(temp_file_path).unlink()


def delete_namespace(namespace: str) -> V1Status:
    v1: CoreV1Api = get_static_client()
    resp = v1.delete_namespace(namespace)
    return resp


def delete_pod(
    pod_name: str,
    namespace: str,
    grace_period: int = 30,
    force: bool = False,
    ignore_not_found: bool = True,
) -> Optional[V1Status]:
    v1: CoreV1Api = get_static_client()
    delete_options = V1DeleteOptions(
        grace_period_seconds=grace_period,
        propagation_policy="Foreground" if force else "Background",
    )
    try:
        resp = v1.delete_namespaced_pod(name=pod_name, namespace=namespace, body=delete_options)
        return resp
    except ApiException as e:
        if e.status == 404 and ignore_not_found:
            print(f"Pod {pod_name} in namespace {namespace} not found, but ignoring as requested.")
            return None
        else:
            raise


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
        temp_bitcoin_data_path = "/tmp/bitcoin_data.tar.gz"
        copy_file_from_pod(namespace, pod_name, temp_bitcoin_data_path, local_file_path)

        print(f"Bitcoin data exported successfully to {local_file_path}")
        cleanup_command = ["rm", temp_bitcoin_data_path]
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


def copy_file_from_pod(namespace, pod_name, pod_path, local_path):
    exec_command = ["cat", pod_path]

    v1 = client.CoreV1Api()

    # Note: We do not specify the container name here; if we pack multiple containers in a pod
    # we will need to change this
    resp = stream(
        v1.connect_get_namespaced_pod_exec,
        pod_name,
        namespace,
        command=exec_command,
        stderr=True,
        stdin=False,
        stdout=True,
        tty=False,
        _preload_content=False,
    )

    with open(local_path, "wb") as local_file:
        while resp.is_open():
            resp.update(timeout=1)
            if resp.peek_stdout():
                local_file.write(resp.read_stdout().encode("utf-8"))
            if resp.peek_stderr():
                print("Error:", resp.read_stderr())

    resp.close()


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


def pod_log(pod_name, container_name=None, follow=False, timestamps=False) -> HTTPResponse:
    sclient = get_static_client()
    try:
        return sclient.read_namespaced_pod_log(
            name=pod_name,
            namespace=get_default_namespace(),
            container=container_name,
            follow=follow,
            timestamps=timestamps,
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

def open_kubeconfig(kubeconfig_path: str = KUBECONFIG) -> dict:
    try:
        with open(kubeconfig_path) as file:
            return yaml.safe_load(file)
    except FileNotFoundError as e:
        raise K8sError(f"Kubeconfig file {kubeconfig_path} not found.") from e
    except yaml.YAMLError as e:
        raise K8sError(f"Error parsing kubeconfig: {e}") from e


def write_kubeconfig(kube_config: dict) -> None:
    dir_name = os.path.dirname(KUBECONFIG)
    try:
        with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False) as temp_file:
            yaml.safe_dump(kube_config, temp_file)
        os.replace(temp_file.name, KUBECONFIG)
    except Exception as e:
        os.remove(temp_file.name)
        raise K8sError(f"Error writing kubeconfig: {KUBECONFIG}") from e
