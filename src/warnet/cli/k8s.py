import os
import subprocess
from importlib.resources import files

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


def get_tanks():
    pods = get_pods()
    tanks = []
    # TODO: filter tanks only!!!!
    for pod in pods.items:
        if "rank" in pod.metadata.labels and pod.metadata.labels["rank"] == "tank":
            tanks.append(
                {
                    "tank": pod.metadata.name,
                    "chain": "regtest",
                    "rpc_host": pod.status.pod_ip,
                    "rpc_port": 18443,
                    "rpc_user": "user",
                    "rpc_password": "password",
                    "init_peers": [],
                }
            )
    return tanks


def run_command(command, stream_output=False, env=None):
    # Merge the current environment with the provided env
    full_env = os.environ.copy()
    if env:
        # Convert all env values to strings (only a safeguard)
        env = {k: str(v) for k, v in env.items()}
        full_env.update(env)

    if stream_output:
        process = subprocess.Popen(
            ["/bin/bash", "-c", command],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
            env=full_env,
        )

        for line in iter(process.stdout.readline, ""):
            print(line, end="")

        process.stdout.close()
        return_code = process.wait()

        if return_code != 0:
            print(f"Command failed with return code {return_code}")
            return False
        return True
    else:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, executable="/bin/bash"
        )
        if result.returncode != 0:
            print(f"Error: {result.stderr}")
            return False
        print(result.stdout)
        return True


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