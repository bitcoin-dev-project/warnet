import io
import logging
import re
import time
from pathlib import Path
from typing import cast

import yaml
from backends import BackendInterface, ServiceType
from cli.image import build_image
from kubernetes import client, config
from kubernetes.client.models.v1_pod import V1Pod
from kubernetes.client.rest import ApiException
from kubernetes.stream import stream
from warnet.lnnode import LNNode
from warnet.status import RunningStatus
from warnet.tank import Tank
from warnet.utils import default_bitcoin_conf_args, parse_raw_messages

DOCKER_REGISTRY_CORE = "bitcoindevproject/bitcoin"
DOCKER_REGISTRY_LND = "lightninglabs/lnd:v0.17.0-beta"
LOCAL_REGISTRY = "warnet/bitcoin-core"
POD_PREFIX = "tank"
BITCOIN_CONTAINER_NAME = "bitcoin"
LN_CONTAINER_NAME = "ln"


logger = logging.getLogger("KubernetesBackend")


class KubernetesBackend(BackendInterface):
    def __init__(self, config_dir: Path, network_name: str, logs_pod="fluentd") -> None:
        super().__init__(config_dir)
        # assumes the warnet rpc server is always
        # running inside a k8s cluster as a statefulset
        config.load_incluster_config()
        self.client = client.CoreV1Api()
        self.namespace = "warnet"
        self.logs_pod = logs_pod
        self.network_name = network_name
        self.log = logger

    def build(self) -> bool:
        # TODO: just return true for now, this is so we can be running either docker or k8s as a backend
        # on the same branch
        return True

    def up(self, warnet) -> bool:
        self.deploy_pods(warnet)
        return True

    def down(self, warnet) -> bool:
        """
        Bring an exsiting network down.
            e.g. `k delete -f warnet-tanks.yaml`
        """

        for tank in warnet.tanks:
            pod_name = self.get_pod_name(tank.index, ServiceType.BITCOIN)
            self.client.delete_namespaced_pod(pod_name, self.namespace)
            service_name = f"bitcoind-{POD_PREFIX}-{tank.index:06d}"
            self.client.delete_namespaced_service(service_name, self.namespace)
            if tank.lnnode:
                pod_name = self.get_pod_name(tank.index, ServiceType.LIGHTNING)
                self.client.delete_namespaced_pod(pod_name, self.namespace)
        return True

    def get_file(self, tank_index: int, service: ServiceType, file_path: str):
        """
        Read a file from inside a container
        """
        pod_name = self.get_pod_name(tank_index, service)
        exec_command = ["cat", file_path]

        resp = stream(
            self.client.connect_get_namespaced_pod_exec,
            pod_name,
            self.namespace,
            command=exec_command,
            stderr=True,
            stdin=True,
            stdout=True,
            tty=False,
            _preload_content=False,
            container=BITCOIN_CONTAINER_NAME
            if service == ServiceType.BITCOIN
            else LN_CONTAINER_NAME,
        )

        file = io.BytesIO()
        while resp.is_open():
            resp.update(timeout=1)
            if resp.peek_stdout():
                file.write(resp.read_stdout())
            if resp.peek_stderr():
                raise Exception(
                    "Problem copying file from pod" + resp.read_stderr().decode("utf-8")
                )

        return file.getvalue()

    def get_pod_name(self, tank_index: int, type: ServiceType) -> str:
        if type == ServiceType.LIGHTNING:
            return f"{self.network_name}-{POD_PREFIX}-ln-{tank_index:06d}"
        return f"{self.network_name}-{POD_PREFIX}-{tank_index:06d}"

    def get_pod(self, pod_name: str) -> V1Pod | None:
        try:
            return cast(
                V1Pod, self.client.read_namespaced_pod(name=pod_name, namespace=self.namespace)
            )
        except ApiException as e:
            if e.status == 404:
                return None

    # We could enhance this by checking the pod status as well
    # The following pod phases are available: Pending, Running, Succeeded, Failed, Unknown
    # For example not able to pull image will be a phase of Pending, but the container status will be ErrImagePull
    def get_status(self, tank_index: int, service: ServiceType) -> RunningStatus:
        pod_name = self.get_pod_name(tank_index, service)
        pod = self.get_pod(pod_name)
        # Possible states:
        # 1. pod not found?
        #    -> STOPPED
        # 2. pod phase Succeeded?
        #    -> STOPPED
        # 3. pod phase Failed?
        #    -> FAILED
        # 4. pod phase Unknown?
        #    -> UNKNOWN
        # Pod phase is now "Running" or "Pending"
        #    -> otherwise we need a bug fix, return UNKNOWN
        #
        # The pod is ready if all containers are ready.
        # 5. Pod not ready?
        #    -> PENDING
        # 6. Pod ready?
        #    -> RUNNING
        #
        # Note: we don't know anything about deleted pods so we can't return a status for them.
        # TODO: we could use a kubernetes job to keep the result 🤔

        if pod is None:
            return RunningStatus.STOPPED

        assert pod.status, "Could not get pod status"
        assert pod.status.phase, "Could not get pod status.phase"
        if pod.status.phase == "Succeeded":
            return RunningStatus.STOPPED
        if pod.status.phase == "Failed":
            return RunningStatus.FAILED
        if pod.status.phase == "Unknown":
            return RunningStatus.UNKNOWN
        if pod.status.phase == "Pending":
            return RunningStatus.PENDING

        assert pod.status.phase in ("Running", "Pending"), f"Unknown pod phase {pod.status.phase}"

        # a pod is ready if all containers are ready
        ready = True
        for container in pod.status.container_statuses:
            if container.ready is not True:
                ready = False
                break
        return RunningStatus.RUNNING if ready else RunningStatus.PENDING

    def exec_run(self, tank_index: int, service: ServiceType, cmd: str):
        pod_name = self.get_pod_name(tank_index, service)
        if service == ServiceType.BITCOIN:
            exec_cmd = ["/bin/bash", "-c", f"{cmd}"]
        elif service == ServiceType.LIGHTNING:
            exec_cmd = ["/bin/sh", "-c", f"{cmd}"]
        self.log.debug(f"Running {exec_cmd=:} on {tank_index=:}")
        result = stream(
            self.client.connect_get_namespaced_pod_exec,
            pod_name,
            self.namespace,
            container=BITCOIN_CONTAINER_NAME
            if service == ServiceType.BITCOIN
            else LN_CONTAINER_NAME,
            command=exec_cmd,
            stderr=True,
            stdin=False,
            stdout=True,
            tty=False,
            # Avoid preloading the content to keep JSON intact
            _preload_content=False,
        )
        # TODO: stream result is just a string, so there is no error code to check
        # ideally, we use a method where we can check for an error code, otherwise we will
        # need to check for errors in the string (meh)
        #
        # if result.exit_code != 0:
        #     raise Exception(
        #         f"Command failed with exit code {result.exit_code}: {result.output.decode('utf-8')}"
        #     )
        result.run_forever()
        result = result.read_all()
        return result

    def get_bitcoin_debug_log(self, tank_index: int):
        pod_name = self.get_pod_name(tank_index, ServiceType.BITCOIN)
        logs = self.client.read_namespaced_pod_log(
            name=pod_name,
            namespace=self.namespace,
            container=BITCOIN_CONTAINER_NAME,
        )
        return logs

    def ln_cli(self, tank: Tank, command: list[str]):
        if tank.lnnode is None:
            raise Exception("No LN node configured for tank")
        cmd = tank.lnnode.generate_cli_command(command)
        self.log.debug(f"Running lncli {cmd=:} on {tank.index=:}")
        return self.exec_run(tank.index, ServiceType.LIGHTNING, cmd)

    def get_bitcoin_cli(self, tank: Tank, method: str, params=None):
        if params:
            cmd = f"bitcoin-cli -regtest -rpcuser={tank.rpc_user} -rpcport={tank.rpc_port} -rpcpassword={tank.rpc_password} {method} {' '.join(map(str, params))}"
        else:
            cmd = f"bitcoin-cli -regtest -rpcuser={tank.rpc_user} -rpcport={tank.rpc_port} -rpcpassword={tank.rpc_password} {method}"
        self.log.debug(f"Running bitcoin-cli {cmd=:} on {tank.index=:}")
        return self.exec_run(tank.index, ServiceType.BITCOIN, cmd)

    def get_messages(
        self,
        tank_index: int,
        b_ipv4: str,
        bitcoin_network: str = "regtest",
    ):
        subdir = "/" if bitcoin_network == "main" else f"{bitcoin_network}/"
        cmd = f"ls /home/bitcoin/.bitcoin/{subdir}message_capture"
        self.log.debug(f"Running {cmd=:} on {tank_index=:}")
        dirs = self.exec_run(
            tank_index,
            ServiceType.BITCOIN,
            cmd,
        )
        dirs = dirs.splitlines()
        messages = []

        for dir_name in dirs:
            if b_ipv4 in dir_name:
                for file, outbound in [["msgs_recv.dat", False], ["msgs_sent.dat", True]]:
                    # Fetch the file contents from the container
                    file_path = f"/home/bitcoin/.bitcoin/{subdir}message_capture/{dir_name}/{file}"
                    blob = self.exec_run(
                        tank_index, ServiceType.BITCOIN, f"cat {file_path}", self.namespace
                    )

                    # Parse the blob
                    json = parse_raw_messages(blob, outbound)
                    messages = messages + json

        messages.sort(key=lambda x: x["time"])
        return messages

    def logs_grep(self, pattern: str, network: str):
        compiled_pattern = re.compile(pattern)
        matching_logs = []

        pods = self.client.list_namespaced_pod(self.namespace)

        # TODO: Can adapt to only search lnd or bitcoind containers?
        relevant_pods = [pod for pod in pods.items if "warnet" in pod.metadata.name]

        # Iterate through the filtered pods to fetch and search logs
        for pod in relevant_pods:
            try:
                log_stream = self.client.read_namespaced_pod_log(
                    name=pod.metadata.name,
                    namespace=self.namespace,
                    timestamps=True,
                    _preload_content=False,
                )

                for log_entry in log_stream:
                    log_entry_str = log_entry.decode("utf-8").strip()
                    if compiled_pattern.search(log_entry_str):
                        matching_logs.append(log_entry_str)
            except ApiException as e:
                print(f"Error fetching logs for pod {pod.metadata.name}: {e}")

        return "\n".join(matching_logs)

    def generate_deployment_file(self, warnet):
        """
        TODO: implement this
        """
        pass

    def warnet_from_deployment(self, warnet):
        # Get pod details from Kubernetes deployment
        pods_by_name = {}
        pods = self.client.list_namespaced_pod(namespace=self.namespace)
        for pod in pods.items:
            pods_by_name[pod.metadata.name] = pod
        for pod in pods.items:
            tank = self.tank_from_deployment(pod, pods_by_name, warnet)
            if tank is not None:
                warnet.tanks.append(tank)
        self.log.debug("reated warnet from deployment")

    def tank_from_deployment(self, pod, pods_by_name, warnet):
        rex = rf"{warnet.network_name}-{POD_PREFIX}-([0-9]{{6}})"
        match = re.match(rex, pod.metadata.name)
        if match is None:
            return None

        index = int(match.group(1))
        tank = Tank(index, warnet.config_dir, warnet)

        # Get IP address from pod status
        tank.ipv4 = pod.status.pod_ip

        # Extract version details from pod spec (assuming it's passed as environment variables)
        for container in pod.spec.containers:
            if container.name == BITCOIN_CONTAINER_NAME and container.env is None:
                continue

            c_repo = None
            c_branch = None
            for env in container.env:
                match env.name:
                    case "BITCOIN_VERSION":
                        tank.version = env.value
                    case "REPO":
                        c_repo = env.value
                    case "BRANCH":
                        c_branch = env.value
                if c_repo and c_branch:
                    tank.version = f"{c_repo}#{c_branch}"
        self.log.debug(f"Created tank {tank.index} from deployment: {tank=:}")

        # check if we can find a corresponding lnd pod
        lnd_pod = pods_by_name.get(self.get_pod_name(index, ServiceType.LIGHTNING))
        if lnd_pod:
            tank.lnnode = LNNode(warnet, tank, "lnd", self)
            tank.lnnode.ipv4 = lnd_pod.status.pod_ip
            self.log.debug(
                f"Created lightning for tank {tank.index} from deployment {tank.lnnode=:}"
            )

        return tank

    def default_bitcoind_config_args(self, tank):
        defaults = default_bitcoin_conf_args()
        defaults += f" -rpcuser={tank.rpc_user}"
        defaults += f" -rpcpassword={tank.rpc_password}"
        defaults += f" -rpcport={tank.rpc_port}"
        defaults += f" -zmqpubrawblock=tcp://0.0.0.0:{tank.zmqblockport}"
        defaults += f" -zmqpubrawtx=tcp://0.0.0.0:{tank.zmqtxport}"
        return defaults

    def create_bitcoind_container(self, tank) -> client.V1Container:
        self.log.debug(f"Creating bitcoind container for tank {tank.index}")
        container_name = BITCOIN_CONTAINER_NAME
        container_image = None

        # Prebuilt image
        if tank.image:
            container_image = tank.image
        # On-demand built image
        elif "/" and "#" in tank.version:
            # We don't have docker installed on the RPC server, where this code will be run from,
            # and it's currently unclear to me if having the RPC pod build images is a good idea.
            # Don't support this for now in CI by disabling in the workflow.

            # This can be re-enabled by enabling in the workflow file and installing docker and
            # docker-buildx on the rpc server image.

            # it's a git branch, building step is necessary
            repo, branch = tank.version.split("#")
            build_image(
                repo,
                branch,
                LOCAL_REGISTRY,
                branch,
                tank.DEFAULT_BUILD_ARGS + tank.extra_build_args,
                arches="amd64",
            )
        # Prebuilt major version
        else:
            container_image = f"{DOCKER_REGISTRY_CORE}:{tank.version}"

        bitcoind_options = self.default_bitcoind_config_args(tank)
        bitcoind_options += f" {tank.conf}"
        container_env = [client.V1EnvVar(name="BITCOIN_ARGS", value=bitcoind_options)]

        bitcoind_container = client.V1Container(
            name=container_name,
            image=container_image,
            env=container_env,
            liveness_probe=client.V1Probe(
                failure_threshold=3,
                initial_delay_seconds=5,
                period_seconds=5,
                timeout_seconds=1,
                _exec=client.V1ExecAction(command=["pidof", "bitcoind"]),
            ),
            readiness_probe=client.V1Probe(
                failure_threshold=1,
                initial_delay_seconds=0,
                period_seconds=1,
                timeout_seconds=1,
                tcp_socket=client.V1TCPSocketAction(port=tank.rpc_port),
            ),
            security_context=client.V1SecurityContext(
                privileged=True,
                capabilities=client.V1Capabilities(add=["NET_ADMIN", "NET_RAW"]),
            ),
        )
        self.log.debug(
            f"Created bitcoind container for tank {tank.index} using {bitcoind_options=:}"
        )
        return bitcoind_container

    def create_lnd_container(self, tank, bitcoind_service_name) -> client.V1Container:
        # These args are appended to the Dockerfile `ENTRYPOINT ["lnd"]`
        bitcoind_rpc_host = f"{bitcoind_service_name}.{self.namespace}"
        lightning_dns = f"lightning-{tank.index}.{self.namespace}"
        args = [
            "--noseedbackup",
            "--norest",
            "--debuglevel=debug",
            "--accept-keysend",
            "--bitcoin.active",
            "--bitcoin.regtest",
            "--bitcoin.node=bitcoind",
            f"--bitcoind.rpcuser={tank.rpc_user}",
            f"--bitcoind.rpcpass={tank.rpc_password}",
            f"--bitcoind.rpchost={bitcoind_rpc_host}:{tank.rpc_port}",
            f"--bitcoind.zmqpubrawblock={bitcoind_rpc_host}:{tank.zmqblockport}",
            f"--bitcoind.zmqpubrawtx={bitcoind_rpc_host}:{tank.zmqtxport}",
            f"--rpclisten=0.0.0.0:{tank.lnnode.rpc_port}",
            f"--externalhosts={lightning_dns}",
            f"--alias={tank.index}",
        ]
        self.log.debug(f"Creating lightning container for tank {tank.index} using {args=:}")
        lightning_container = client.V1Container(
            name=LN_CONTAINER_NAME,
            image=f"{DOCKER_REGISTRY_LND}",
            args=args,
            env=[
                client.V1EnvVar(name="LND_NETWORK", value="regtest"),
            ],
            readiness_probe=client.V1Probe(
                failure_threshold=1,
                success_threshold=3,
                initial_delay_seconds=1,
                period_seconds=2,
                timeout_seconds=2,
                _exec=client.V1ExecAction(
                    command=["/bin/sh", "-c", "lncli --network=regtest getinfo"]
                ),
            ),
            security_context=client.V1SecurityContext(
                privileged=True,
                capabilities=client.V1Capabilities(add=["NET_ADMIN", "NET_RAW"]),
            ),
        )
        self.log.debug(f"Created lightning container for tank {tank.index}")
        return lightning_container

    def create_pod_object(
        self, tank: Tank, container: client.V1Container, name: str
    ) -> client.V1Pod:
        # Create and return a Pod object
        # TODO: pass a custom namespace , e.g. different warnet sims can be deployed into diff namespaces

        return client.V1Pod(
            api_version="v1",
            kind="Pod",
            metadata=client.V1ObjectMeta(
                name=name,
                namespace=self.namespace,
                labels={
                    "app": name,
                    "network": tank.warnet.network_name,
                },
            ),
            spec=client.V1PodSpec(
                # Might need some more thinking on the pod restart policy, setting to Never for now
                # This means if a node has a problem it dies
                restart_policy="OnFailure",
                containers=[container],
            ),
        )

    def create_bitcoind_service(self, tank) -> client.V1Service:
        service_name = f"bitcoind-{POD_PREFIX}-{tank.index:06d}"
        self.log.debug(f"Creating bitcoind service {service_name} for tank {tank.index}")
        service = client.V1Service(
            api_version="v1",
            kind="Service",
            metadata=client.V1ObjectMeta(
                name=service_name,
                labels={
                    "app": self.get_pod_name(tank.index, ServiceType.BITCOIN),
                    "network": tank.warnet.network_name,
                },
            ),
            spec=client.V1ServiceSpec(
                selector={"app": self.get_pod_name(tank.index, ServiceType.BITCOIN)},
                publish_not_ready_addresses=True,
                ports=[
                    # TODO: do we need to add 18444 here too?
                    client.V1ServicePort(port=tank.rpc_port, target_port=tank.rpc_port, name="rpc"),
                    client.V1ServicePort(
                        port=tank.zmqblockport, target_port=tank.zmqblockport, name="zmqblock"
                    ),
                    client.V1ServicePort(
                        port=tank.zmqtxport, target_port=tank.zmqtxport, name="zmqtx"
                    ),
                ],
            ),
        )
        self.log.debug(f"Created bitcoind service {service_name} for tank {tank.index}")
        return service

    def create_lightning_service(self, tank) -> client.V1Service:
        service_name = f"lightning-{tank.index}"
        self.log.debug(f"Creating lightning service {service_name} for tank {tank.index}")
        service = client.V1Service(
            api_version="v1",
            kind="Service",
            metadata=client.V1ObjectMeta(
                name=service_name,
                labels={
                    "app": self.get_pod_name(tank.index, ServiceType.LIGHTNING),
                    "network": tank.warnet.network_name,
                },
            ),
            spec=client.V1ServiceSpec(
                selector={"app": self.get_pod_name(tank.index, ServiceType.LIGHTNING)},
                cluster_ip="None",
                ports=[
                    client.V1ServicePort(
                        port=tank.lnnode.rpc_port, target_port=tank.lnnode.rpc_port, name="rpc"
                    ),
                ],
                publish_not_ready_addresses=True,
            ),
        )
        self.log.debug(f"Created lightning service {service_name} for tank {tank.index}")
        return service

    def fetch_ip_address(self, tank) -> bool:
        pod_ip = None
        while not pod_ip:
            pod_name = self.get_pod_name(tank.index, ServiceType.BITCOIN)
            pod = self.get_pod(pod_name)
            if pod is None or pod.status is None or getattr(pod.status, "pod_ip", None) is None:
                print(f"Waiting for tank {tank.index} response or tank IP...")
                time.sleep(3)
                continue
            pod_ip = pod.status.pod_ip

        tank.ipv4 = pod_ip
        return True

    def deploy_pods(self, warnet):
        # TODO: this is pretty hack right now, ideally it should mirror
        # a similar workflow to the docker backend:
        # 1. read graph file, turn graph file into k8s resources, deploy the resources
        tank_resource_files = []
        self.log.debug("Deploying pods")
        for tank in warnet.tanks:
            # Create and deploy bitcoind pod and service
            bitcoind_container = self.create_bitcoind_container(tank)
            bitcoind_pod = self.create_pod_object(
                tank, bitcoind_container, self.get_pod_name(tank.index, ServiceType.BITCOIN)
            )
            bitcoind_service = self.create_bitcoind_service(tank)
            self.client.create_namespaced_pod(namespace=self.namespace, body=bitcoind_pod)
            # delete the service if it already exists, ignore 404
            try:
                self.client.delete_namespaced_service(
                    name=bitcoind_service.metadata.name, namespace=self.namespace
                )
            except ApiException as e:
                if e.status != 404:
                    raise e
            self.client.create_namespaced_service(namespace=self.namespace, body=bitcoind_service)

            # Create and deploy LND pod
            if tank.lnnode:
                lnd_container = self.create_lnd_container(tank, bitcoind_service.metadata.name)
                lnd_pod = self.create_pod_object(
                    tank, lnd_container, self.get_pod_name(tank.index, ServiceType.LIGHTNING)
                )
                self.client.create_namespaced_pod(namespace=self.namespace, body=lnd_pod)
                lightning_service = self.create_lightning_service(tank)
                try:
                    self.client.delete_namespaced_service(
                        name=lightning_service.metadata.name, namespace=self.namespace
                    )
                except ApiException as e:
                    if e.status != 404:
                        raise e
                self.client.create_namespaced_service(
                    namespace=self.namespace, body=lightning_service
                )

        self.log.debug("Containers and services created. Configuring IP addresses")
        # now that the pods have had a second to create,
        # get the ips and set them on the tanks

        # TODO: this is really hacky, should probably just update the generate_ipv4 function at some point
        # by moving it into the base class
        for tank in warnet.tanks:
            self.fetch_ip_address(tank)
            print(f"Tank {tank.index} created")

        with open(warnet.config_dir / "warnet-tanks.yaml", "w") as f:
            for pod in tank_resource_files:
                yaml.dump(pod.to_dict(), f)
                f.write("---\n")  # separator for multiple resources
            self.log.info("Pod definitions saved to warnet-tanks.yaml")
