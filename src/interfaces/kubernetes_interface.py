from .interfaces import ContainerInterface
from pathlib import Path

from kubernetes import client, config
from kubernetes.client.models.v1_pod import V1Pod
from kubernetes.stream import stream

import time
import re
import yaml

from typing import cast

from warnet.tank import Tank, CONTAINER_PREFIX_BITCOIND
from warnet.utils import parse_raw_messages, default_bitcoin_conf_args

DOCKER_REGISTRY = "bitcoindevproject/k8s-bitcoin-core"

class KubernetesInterface(ContainerInterface):

    def __init__(self, config_dir: Path, namespace = "default", logs_pod = "fluentd") -> None:
        super().__init__(config_dir)
        # assumes the warnet rpc server is always
        # running inside a k8s cluster as a statefulset
        config.load_incluster_config()
        self.client = client.CoreV1Api()
        self.namespace = namespace
        self.logs_pod = logs_pod

    def build(self) -> bool:
        # TODO: just return true for now, this is so we can be running either docker or k8s as a backend
        # on the same branch
        return True

    def up(self, warnet) -> bool:
        self.deploy_pods(warnet)
        return True

    def down(self) -> bool:
        """
        Bring an exsiting network down.
            e.g. `docker compose down`
        """
        raise NotImplementedError("This method isn't implemented yet")
    
    def get_file(self, container_name: str, file_path: str):
        """
        Read a file from inside a container
        """
        raise NotImplementedError("This method isn't implemented yet")

    def get_container(self, container_name: str) -> V1Pod:
        return cast(V1Pod, self.client.read_namespaced_pod(name=container_name, namespace="default"))

    def exec_run(self, container_name: str, cmd: str, user: str = "root"):

        # k8s doesn't let us run exec commands as a user, but we can use su
        # because its installed in the bitcoin containers. we will need to rework
        # this command if we decided to remove gosu from the containers
        # TODO: change this if we remove gosu
        exec_cmd = ["/bin/sh", "-c", f"su - {user} -c '{cmd}'"]
        result = stream(
                self.client.connect_get_namespaced_pod_exec, container_name,
                "default",
                command=exec_cmd,
                stderr=True,
                stdin=False,
                stdout=True,
                tty=False
        )
        # TODO: stream result is just a string, so there is no error code to check
        # ideally, we use a method where we can check for an error code, otherwise we will
        # need to check for errors in the string (meh)
        #
        # if result.exit_code != 0:
        #     raise Exception(
        #         f"Command failed with exit code {result.exit_code}: {result.output.decode('utf-8')}"
        #     )
        return result

    def get_bitcoin_debug_log(self, container_name: str):
        logs = self.client.read_namespaced_pod_log(
            name=container_name,
            namespace="default",
        )
        return logs

    def get_bitcoin_cli(self, tank: Tank, method: str, params=None):
        if params:
            cmd = f"bitcoin-cli -regtest -rpcuser={tank.rpc_user} -rpcport={tank.rpc_port} -rpcpassword={tank.rpc_password} {method} {' '.join(map(str, params))}"
        else:
            cmd = f"bitcoin-cli -regtest -rpcuser={tank.rpc_user} -rpcport={tank.rpc_port} -rpcpassword={tank.rpc_password} {method}"
        return self.exec_run(tank.container_name, cmd, user="bitcoin")

    def get_messages(self, a_name: str, b_ipv4: str, bitcoin_network: str = "regtest", namespace: str = "default"):
        subdir = "/" if bitcoin_network == "main" else f"{bitcoin_network}/"
        dirs = self.exec_run(a_name, f"ls /home/bitcoin/.bitcoin/{subdir}message_capture", namespace)
        dirs = dirs.splitlines()
        messages = []

        for dir_name in dirs:
            if b_ipv4 in dir_name:
                for file, outbound in [["msgs_recv.dat", False], ["msgs_sent.dat", True]]:
                    # Fetch the file contents from the container
                    file_path = f"/home/bitcoin/.bitcoin/{subdir}message_capture/{dir_name}/{file}"
                    blob = self.exec_run(a_name, f"cat {file_path}", namespace)

                    # Parse the blob
                    json = parse_raw_messages(blob, outbound)
                    messages = messages + json

        messages.sort(key=lambda x: x["time"])
        return messages

    # TODO: stop using fluentd and instead interate through all pods?
    def logs_grep(self, pattern: str, network: str):
        compiled_pattern = re.compile(pattern)

        # Fetch the logs from the pod
        log_stream = self.client.read_namespaced_pod_log(
                name=self.logs_pod ,
                namespace=self.namespace,
                timestamps=True,
                _preload_content=False,
        )

        matching_logs = []
        for log_entry in log_stream:
            log_entry_str = log_entry.decode('utf-8').strip()
            if compiled_pattern.search(log_entry_str):
                matching_logs.append(log_entry_str)

        return '\n'.join(matching_logs)

    def generate_deployment_file(self, warnet):
        """
        TODO: implement this
        """
        pass

    def warnet_from_deployment(self, warnet):
        # Get pod details from Kubernetes deployment
        pods = self.client.list_namespaced_pod(namespace="default")
        for pod in pods.items:
            tank = self.tank_from_deployment(pod, warnet)
            if tank is not None:
                warnet.tanks.append(tank)

    def tank_from_deployment(self, pod, warnet):
        rex = fr"{warnet.network_name}-{CONTAINER_PREFIX_BITCOIND}-([0-9]{{6}})"
        match = re.match(rex, pod.metadata.name)
        if match is None:
            return None

        index = int(match.group(1))
        t = Tank(index, warnet.config_dir, warnet)

        # Get IP address from pod status
        t._ipv4 = pod.status.pod_ip

        print(pod)
        # Extract version details from pod spec (assuming it's passed as environment variables)
        for container in pod.spec.containers:
            for env in container.env:
                if env.name == "BITCOIN_VERSION":
                    t.version = env.value
                elif env.name == "REPO":
                    repo = env.value
                elif env.name == "BRANCH":
                    branch = env.value
        if not hasattr(t, 'version'):
            t.version = f"{repo}#{branch}"

        return t
    
    def default_config_args(self, tank):
        defaults = default_bitcoin_conf_args()
        defaults += f" -rpcuser={tank.rpc_user}"
        defaults += f" -rpcpassword={tank.rpc_password}"
        defaults += f" -rpcport={tank.rpc_port}"
        return defaults


    def create_pod_object(self, tank):
        # Create and return a Pod object
        # Right now, we can only use images from a registry. Its likely even when we figure out a way
        # to support custom builds, they will also be pushed to a registry first, either a local in cluster one
        # or one under the users control
        # TODO: support custom builds
        # TODO: pass a custom namespace , e.g. different warnet sims can be deployed into diff namespaces
        return client.V1Pod(
            api_version="v1",
            kind="Pod",
            metadata=client.V1ObjectMeta(name=tank.container_name, namespace="default"),
            spec=client.V1PodSpec(
                # Might need some more thinking on the pod restart policy, setting to Never for now
                # This means if a node has a problem it dies
                restart_policy="Never",
                containers=[
                    client.V1Container(
                        name=tank.container_name,
                        image=f"{DOCKER_REGISTRY}:{tank.version}",
                        env=[
                            client.V1EnvVar(
                                name="BITCOIN_ARGS",
                                value=self.default_config_args(tank)
                            )
                        ],
                        # TODO: this doesnt seem to work as expected? 
                        # missing the exec field.
                        # liveness_probe=client.V1Probe(
                        #     failure_threshold=3,
                        #     initial_delay_seconds=5,
                        #     period_seconds=5,
                        #     timeout_seconds=1,
                        #     exec=client.V1ExecAction(
                        #         command=["pidof", "bitcoind"]
                        #     )
                        # ),
                        security_context=client.V1SecurityContext(
                            privileged=True,
                            capabilities=client.V1Capabilities(
                                add=["NET_ADMIN", "NET_RAW"]
                            )
                        )
                    )
                ]
            )
        )

    def deploy_pods(self, warnet):

        # TODO: this is pretty hack right now, ideally it should mirror
        # a similar workflow to the docker backend:
        # 1. read graph file, turn graph file into k8s resources, deploy the resources
        tank_resource_files = []
        for tank in warnet.tanks:
            pod = self.create_pod_object(tank)
            tank_resource_files.append(pod)
            # TODO: dont hardcode namespace, should be specific to a warnet deployment
            resp = self.client.create_namespaced_pod(namespace="default", body=pod)

        # now that the pods have had a second to create, 
        # get the ips and set them on the tanks

        # TODO: this is really hacky, should probably just update the generage_ipv4 function at some point
        # by moving it into the base class
        for tank in warnet.tanks:
            pod_ip = None
            while not pod_ip:
                response = self.get_container(tank.container_name)
                pod_ip = response.status.pod_ip
                if not pod_ip:
                    print("Waiting for pod IP...")
                    time.sleep(3)  # sleep for 5 seconds

            tank._ipv4 = pod_ip
            print(f"Tank {tank.container_name} created")

        with open(warnet.config_dir / 'warnet-tanks.yaml', 'w') as f:
            for pod in tank_resource_files:
                yaml.dump(pod.to_dict(), f)
                f.write("---\n")  # separator for multiple resources
            print("Pod definitions saved to warnet-tanks.yaml")
