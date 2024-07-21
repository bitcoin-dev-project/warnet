import base64
import logging
import re
import subprocess
import time
from pathlib import Path
from typing import cast

import yaml
from kubernetes import client, config
from kubernetes.client.exceptions import ApiValueError
from kubernetes.client.models.v1_pod import V1Pod
from kubernetes.client.models.v1_service import V1Service
from kubernetes.client.rest import ApiException
from kubernetes.dynamic import DynamicClient
from kubernetes.dynamic.exceptions import NotFoundError, ResourceNotFoundError
from kubernetes.stream import stream
from warnet.cli.image import build_image
from warnet.services import SERVICES, ServiceType
from warnet.status import RunningStatus
from warnet.tank import Tank
from warnet.utils import parse_raw_messages

DOCKER_REGISTRY_CORE = "bitcoindevproject/bitcoin"
LOCAL_REGISTRY = "warnet/bitcoin-core"

POD_PREFIX = "tank"
BITCOIN_CONTAINER_NAME = "bitcoin"
LN_CONTAINER_NAME = "ln"
LN_CB_CONTAINER_NAME = "ln-cb"
MAIN_NAMESPACE = "warnet"
PROMETHEUS_METRICS_PORT = 9332
LND_MOUNT_PATH = "/root/.lnd"


logger = logging.getLogger("k8s")


class KubernetesBackend:
    def __init__(self, config_dir: Path, network_name: str, logs_pod="fluentd") -> None:
        # assumes the warnet rpc server is always
        # running inside a k8s cluster as a statefulset
        config.load_incluster_config()
        self.client = client.CoreV1Api()
        self.dynamic_client = DynamicClient(client.ApiClient())
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
        Bring an existing network down.
            e.g. `k delete -f warnet-tanks.yaml`
        """

        for tank in warnet.tanks:
            self.client.delete_namespaced_pod(
                self.get_pod_name(tank.index, ServiceType.BITCOIN), self.namespace
            )
            self.client.delete_namespaced_service(
                self.get_service_name(tank.index, ServiceType.BITCOIN), self.namespace
            )
            if tank.lnnode:
                self.client.delete_namespaced_pod(
                    self.get_pod_name(tank.index, ServiceType.LIGHTNING), self.namespace
                )
                self.client.delete_namespaced_service(
                    self.get_service_name(tank.index, ServiceType.LIGHTNING), self.namespace
                )

        self.remove_prometheus_service_monitors(warnet.tanks)

        for service_name in warnet.services:
            try:
                self.client.delete_namespaced_pod(
                    self.get_service_pod_name(SERVICES[service_name]["container_name_suffix"]),
                    self.namespace,
                )
                self.client.delete_namespaced_service(
                    self.get_service_service_name(SERVICES[service_name]["container_name_suffix"]),
                    self.namespace,
                )
            except Exception as e:
                self.log.error(f"Could not delete service: {service_name}:\n{e}")

        return True

    def get_file(self, tank_index: int, service: ServiceType, file_path: str):
        """
        Read a file from inside a container
        """
        pod_name = self.get_pod_name(tank_index, service)
        exec_command = ["sh", "-c", f'cat "{file_path}" | base64']

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

        base64_encoded_data = ""
        while resp.is_open():
            resp.update(timeout=1)
            if resp.peek_stdout():
                base64_encoded_data += resp.read_stdout()
            if resp.peek_stderr():
                stderr_output = resp.read_stderr()
                logger.error(f"STDERR: {stderr_output}")
                raise Exception(f"Problem copying file from pod: {stderr_output}")

        decoded_bytes = base64.b64decode(base64_encoded_data)
        return decoded_bytes

    def get_service_pod_name(self, suffix: str) -> str:
        return f"{self.network_name}-{suffix}"

    def get_service_service_name(self, suffix: str) -> str:
        return f"{self.network_name}-{suffix}-service"

    def get_pod_name(self, tank_index: int, type: ServiceType) -> str:
        if type == ServiceType.LIGHTNING or type == ServiceType.CIRCUITBREAKER:
            return f"{self.network_name}-{POD_PREFIX}-ln-{tank_index:06d}"
        return f"{self.network_name}-{POD_PREFIX}-{tank_index:06d}"

    def get_service_name(self, tank_index: int, type: ServiceType) -> str:
        return f"{self.get_pod_name(tank_index, type)}-service"

    def get_pod(self, pod_name: str) -> V1Pod | None:
        try:
            return cast(
                V1Pod, self.client.read_namespaced_pod(name=pod_name, namespace=self.namespace)
            )
        except ApiException as e:
            if e.status == 404:
                return None

    def get_service(self, service_name: str) -> V1Service | None:
        try:
            return cast(
                V1Service,
                self.client.read_namespaced_service(name=service_name, namespace=self.namespace),
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
        exec_cmd = ["/bin/sh", "-c", f"{cmd}"]
        self.log.debug(f"Running {exec_cmd=:} on {tank_index=:}")
        if service == ServiceType.BITCOIN:
            container = BITCOIN_CONTAINER_NAME
        if service == ServiceType.LIGHTNING:
            container = LN_CONTAINER_NAME
        if service == ServiceType.CIRCUITBREAKER:
            container = LN_CB_CONTAINER_NAME
        result = stream(
            self.client.connect_get_namespaced_pod_exec,
            pod_name,
            self.namespace,
            container=container,
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

    def ln_pub_key(self, tank) -> str:
        if tank.lnnode is None:
            raise Exception("No LN node configured for tank")
        self.log.debug(f"Getting pub key for tank {tank.index}")
        return tank.lnnode.get_pub_key()

    def get_bitcoin_cli(self, tank: Tank, method: str, params=None):
        if params:
            cmd = f"bitcoin-cli -regtest -rpcuser={tank.rpc_user} -rpcport={tank.rpc_port} -rpcpassword={tank.rpc_password} {method} {' '.join(map(str, params))}"
        else:
            cmd = f"bitcoin-cli -regtest -rpcuser={tank.rpc_user} -rpcport={tank.rpc_port} -rpcpassword={tank.rpc_password} {method}"
        self.log.debug(f"Running bitcoin-cli {cmd=:} on {tank.index=:}")
        return self.exec_run(tank.index, ServiceType.BITCOIN, cmd)

    def get_messages(
        self,
        a_index: int,
        b_index: int,
        bitcoin_network: str = "regtest",
    ):
        b_pod = self.get_pod(self.get_pod_name(b_index, ServiceType.BITCOIN))
        b_service = self.get_service(self.get_service_name(b_index, ServiceType.BITCOIN))
        subdir = "/" if bitcoin_network == "main" else f"{bitcoin_network}/"
        base_dir = f"/root/.bitcoin/{subdir}message_capture"
        cmd = f"ls {base_dir}"
        self.log.debug(f"Running {cmd=:} on {a_index=:}")
        dirs = self.exec_run(
            a_index,
            ServiceType.BITCOIN,
            cmd,
        )
        dirs = dirs.splitlines()
        self.log.debug(f"Got dirs: {dirs}")
        messages = []

        for dir_name in dirs:
            if b_pod.status.pod_ip in dir_name or b_service.spec.cluster_ip in dir_name:
                for file, outbound in [["msgs_recv.dat", False], ["msgs_sent.dat", True]]:
                    # Fetch the file contents from the container
                    file_path = f"{base_dir}/{dir_name}/{file}"
                    blob = self.get_file(a_index, ServiceType.BITCOIN, f"{file_path}")
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
                    container=BITCOIN_CONTAINER_NAME,
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

    def create_bitcoind_container(self, tank: Tank) -> client.V1Container:
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
                tank.DEFAULT_BUILD_ARGS + tank.build_args,
                arches="amd64",
            )
        # Prebuilt major version
        else:
            container_image = f"{DOCKER_REGISTRY_CORE}:{tank.version}"

        peers = [
            self.get_service_name(dst_index, ServiceType.BITCOIN) for dst_index in tank.init_peers
        ]
        bitcoind_options = tank.get_bitcoin_conf(peers)
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

    def create_prometheus_container(self, tank) -> client.V1Container:
        return client.V1Container(
            name="prometheus",
            image="jvstein/bitcoin-prometheus-exporter:latest",
            env=[
                client.V1EnvVar(name="BITCOIN_RPC_HOST", value="127.0.0.1"),
                client.V1EnvVar(name="BITCOIN_RPC_PORT", value=str(tank.rpc_port)),
                client.V1EnvVar(name="BITCOIN_RPC_USER", value=tank.rpc_user),
                client.V1EnvVar(name="BITCOIN_RPC_PASSWORD", value=tank.rpc_password),
            ],
        )

    def check_logging_crds_installed(self):
        logging_crd_name = "servicemonitors.monitoring.coreos.com"
        api = client.ApiextensionsV1Api()
        crds = api.list_custom_resource_definition()
        return bool(any(crd.metadata.name == logging_crd_name for crd in crds.items))

    def apply_prometheus_service_monitors(self, tanks):
        for tank in tanks:
            if not tank.exporter:
                continue

            service_monitor = {
                "apiVersion": "monitoring.coreos.com/v1",
                "kind": "ServiceMonitor",
                "metadata": {
                    "name": f"warnet-tank-{tank.index:06d}",
                    "namespace": MAIN_NAMESPACE,
                    "labels": {
                        "app.kubernetes.io/name": "bitcoind-metrics",
                        "release": "prometheus",
                    },
                },
                "spec": {
                    "endpoints": [{"port": "prometheus-metrics"}],
                    "selector": {"matchLabels": {"app": f"warnet-tank-{tank.index:06d}"}},
                },
            }
            # Create the custom resource using the dynamic client
            sc_crd = self.dynamic_client.resources.get(
                api_version="monitoring.coreos.com/v1", kind="ServiceMonitor"
            )
            sc_crd.create(body=service_monitor, namespace=MAIN_NAMESPACE)

    # attempts to delete the service monitors whether they exist or not
    def remove_prometheus_service_monitors(self, tanks):
        for tank in tanks:
            try:
                self.dynamic_client.resources.get(
                    api_version="monitoring.coreos.com/v1", kind="ServiceMonitor"
                ).delete(
                    name=f"warnet-tank-{tank.index:06d}",
                    namespace=MAIN_NAMESPACE,
                )
            except (ResourceNotFoundError, NotFoundError):
                continue

    def get_lnnode_hostname(self, index: int) -> str:
        return f"{self.get_service_name(index, ServiceType.LIGHTNING)}.{self.namespace}"

    def create_ln_container(self, tank, bitcoind_service_name, volume_mounts) -> client.V1Container:
        # These args are appended to the Dockerfile `ENTRYPOINT ["lnd"]`
        bitcoind_rpc_host = f"{bitcoind_service_name}.{self.namespace}"
        lightning_dns = self.get_lnnode_hostname(tank.index)
        args = tank.lnnode.get_conf(lightning_dns, bitcoind_rpc_host)
        self.log.debug(f"Creating lightning container for tank {tank.index} using {args=:}")
        lightning_ready_probe = ""
        if tank.lnnode.impl == "lnd":
            lightning_ready_probe = "lncli --network=regtest getinfo"
        elif tank.lnnode.impl == "cln":
            lightning_ready_probe = "lightning-cli --network=regtest getinfo"
        else:
            raise Exception(
                f"Lightning node implementation {tank.lnnode.impl} for tank {tank.index} not supported"
            )
        lightning_container = client.V1Container(
            name=LN_CONTAINER_NAME,
            image=tank.lnnode.image,
            args=args.split(" "),
            env=[
                client.V1EnvVar(name="LN_IMPL", value=tank.lnnode.impl),
            ],
            readiness_probe=client.V1Probe(
                failure_threshold=1,
                success_threshold=3,
                initial_delay_seconds=10,
                period_seconds=2,
                timeout_seconds=2,
                _exec=client.V1ExecAction(command=["/bin/sh", "-c", lightning_ready_probe]),
            ),
            security_context=client.V1SecurityContext(
                privileged=True,
                capabilities=client.V1Capabilities(add=["NET_ADMIN", "NET_RAW"]),
            ),
            volume_mounts=volume_mounts,
        )
        self.log.debug(f"Created lightning container for tank {tank.index}")
        return lightning_container

    def create_circuitbreaker_container(self, tank, volume_mounts) -> client.V1Container:
        self.log.debug(f"Creating circuitbreaker container for tank {tank.index}")
        cb_container = client.V1Container(
            name=LN_CB_CONTAINER_NAME,
            image=tank.lnnode.cb,
            args=[
                "--network=regtest",
                f"--rpcserver=127.0.0.1:{tank.lnnode.rpc_port}",
                f"--tlscertpath={LND_MOUNT_PATH}/tls.cert",
                f"--macaroonpath={LND_MOUNT_PATH}/data/chain/bitcoin/regtest/admin.macaroon",
            ],
            security_context=client.V1SecurityContext(
                privileged=True,
                capabilities=client.V1Capabilities(add=["NET_ADMIN", "NET_RAW"]),
            ),
            volume_mounts=volume_mounts,
        )
        self.log.debug(f"Created circuitbreaker container for tank {tank.index}")
        return cb_container

    def create_pod_object(
        self,
        tank: Tank,
        containers: list[client.V1Container],
        volumes: list[client.V1Volume],
        name: str,
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
                containers=containers,
                volumes=volumes,
            ),
        )

    def get_tank_ipv4(self, index: int) -> str | None:
        pod_name = self.get_pod_name(index, ServiceType.BITCOIN)
        pod = self.get_pod(pod_name)
        if pod:
            return pod.status.pod_ip
        else:
            return None

    def get_tank_dns_addr(self, index: int) -> str | None:
        service_name = self.get_service_name(index, ServiceType.BITCOIN)
        try:
            self.client.read_namespaced_service(name=service_name, namespace=self.namespace)
        except ApiValueError as e:
            self.log.info(ApiValueError(f"dns addr request for {service_name} raised {str(e)}"))
            return None
        return service_name

    def get_tank_ip_addr(self, index: int) -> str | None:
        service_name = self.get_service_name(index, ServiceType.BITCOIN)
        try:
            endpoints = self.client.read_namespaced_endpoints(
                name=service_name, namespace=self.namespace
            )
        except ApiValueError as e:
            self.log.info(f"ip addr request for {service_name} raised {str(e)}")
            return None

        if len(endpoints.subsets) == 0:
            raise Exception(f"{service_name}'s endpoint does not have an initial subset")
        initial_subset = endpoints.subsets[0]

        if len(initial_subset.addresses) == 0:
            raise Exception(f"{service_name}'s initial subset does not have an initial address")
        initial_address = initial_subset.addresses[0]

        return str(initial_address.ip)

    def create_bitcoind_service(self, tank) -> client.V1Service:
        service_name = self.get_service_name(tank.index, ServiceType.BITCOIN)
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
                    client.V1ServicePort(port=18444, target_port=18444, name="p2p"),
                    client.V1ServicePort(port=tank.rpc_port, target_port=tank.rpc_port, name="rpc"),
                    client.V1ServicePort(
                        port=tank.zmqblockport, target_port=tank.zmqblockport, name="zmqblock"
                    ),
                    client.V1ServicePort(
                        port=tank.zmqtxport, target_port=tank.zmqtxport, name="zmqtx"
                    ),
                    client.V1ServicePort(
                        port=PROMETHEUS_METRICS_PORT,
                        target_port=PROMETHEUS_METRICS_PORT,
                        name="prometheus-metrics",
                    ),
                ],
            ),
        )
        self.log.debug(f"Created bitcoind service {service_name} for tank {tank.index}")
        return service

    def create_lightning_service(self, tank) -> client.V1Service:
        service_name = self.get_service_name(tank.index, ServiceType.LIGHTNING)
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
                tank, [bitcoind_container], [], self.get_pod_name(tank.index, ServiceType.BITCOIN)
            )

            if tank.exporter and self.check_logging_crds_installed():
                prometheus_container = self.create_prometheus_container(tank)
                bitcoind_pod.spec.containers.append(prometheus_container)

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

            # Create and deploy a lightning pod
            if tank.lnnode:
                conts = []
                vols = []
                volume_mounts = []
                if tank.lnnode.cb:
                    # Create a shared volume between containers in the pod
                    volume_name = f"ln-cb-data-{tank.index}"
                    vols.append(
                        client.V1Volume(name=volume_name, empty_dir=client.V1EmptyDirVolumeSource())
                    )
                    volume_mounts.append(
                        client.V1VolumeMount(
                            name=volume_name,
                            mount_path=LND_MOUNT_PATH,
                        )
                    )
                    # Add circuit breaker container
                    conts.append(self.create_circuitbreaker_container(tank, volume_mounts))
                # Add lightning container
                conts.append(
                    self.create_ln_container(tank, bitcoind_service.metadata.name, volume_mounts)
                )
                # Put it all together in a pod
                lnd_pod = self.create_pod_object(
                    tank, conts, vols, self.get_pod_name(tank.index, ServiceType.LIGHTNING)
                )
                self.client.create_namespaced_pod(namespace=self.namespace, body=lnd_pod)
                # Create service for the pod
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

        # add metrics scraping for tanks configured to export metrics
        if self.check_logging_crds_installed():
            self.apply_prometheus_service_monitors(warnet.tanks)

        for service_name in warnet.services:
            try:
                self.service_from_json(SERVICES[service_name])
            except Exception as e:
                self.log.error(f"Error starting service: {service_name}\n{e}")

        self.log.debug("Containers and services created. Configuring IP addresses")
        # now that the pods have had a second to create,
        # get the ips and set them on the tanks

        # TODO: this is really hacky, should probably just update the generate_ipv4 function at some point
        # by moving it into the base class
        for tank in warnet.tanks:
            pod_ip = None
            while not pod_ip:
                pod_name = self.get_pod_name(tank.index, ServiceType.BITCOIN)
                pod = self.get_pod(pod_name)
                if pod is None or pod.status is None or getattr(pod.status, "pod_ip", None) is None:
                    self.log.info("Waiting for pod response or pod IP...")
                    time.sleep(3)
                    continue
                pod_ip = pod.status.pod_ip

            tank._ipv4 = pod_ip
            self.log.debug(f"Tank {tank.index} created")

        with open(warnet.config_dir / "warnet-tanks.yaml", "w") as f:
            for pod in tank_resource_files:
                yaml.dump(pod.to_dict(), f)
                f.write("---\n")  # separator for multiple resources
            self.log.info("Pod definitions saved to warnet-tanks.yaml")

    def wait_for_healthy_tanks(self, warnet, timeout=30):
        """
        Wait for healthy status on all bitcoind nodes
        """
        pass

    def service_from_json(self, obj):
        env = []
        for pair in obj.get("environment", []):
            name, value = pair.split("=")
            env.append(client.V1EnvVar(name=name, value=value))
        volume_mounts = []
        volumes = []
        for vol in obj.get("config_files", []):
            volume_name, mount_path = vol.split(":")
            volume_name = volume_name.replace("/", "")
            volume_mounts.append(client.V1VolumeMount(name=volume_name, mount_path=mount_path))
            volumes.append(
                client.V1Volume(name=volume_name, empty_dir=client.V1EmptyDirVolumeSource())
            )

        service_container = client.V1Container(
            name=self.get_service_pod_name(obj["container_name_suffix"]),
            image=obj["image"],
            env=env,
            security_context=client.V1SecurityContext(
                privileged=True,
                capabilities=client.V1Capabilities(add=["NET_ADMIN", "NET_RAW"]),
            ),
            volume_mounts=volume_mounts,
        )
        sidecar_container = client.V1Container(
            name="sidecar",
            image="pinheadmz/sidecar:latest",
            volume_mounts=volume_mounts,
            ports=[client.V1ContainerPort(container_port=22)],
        )
        service_pod = client.V1Pod(
            api_version="v1",
            kind="Pod",
            metadata=client.V1ObjectMeta(
                name=self.get_service_pod_name(obj["container_name_suffix"]),
                namespace=self.namespace,
                labels={
                    "app": self.get_service_pod_name(obj["container_name_suffix"]),
                    "network": self.network_name,
                },
            ),
            spec=client.V1PodSpec(
                restart_policy="OnFailure",
                containers=[service_container, sidecar_container],
                volumes=volumes,
            ),
        )

        # Do not ever change this variable name. xoxo, --Zip
        service_service = client.V1Service(
            api_version="v1",
            kind="Service",
            metadata=client.V1ObjectMeta(
                name=self.get_service_service_name(obj["container_name_suffix"]),
                labels={
                    "app": self.get_service_pod_name(obj["container_name_suffix"]),
                    "network": self.network_name,
                },
            ),
            spec=client.V1ServiceSpec(
                selector={"app": self.get_service_pod_name(obj["container_name_suffix"])},
                publish_not_ready_addresses=True,
                ports=[
                    client.V1ServicePort(name="ssh", port=22, target_port=22),
                ],
            ),
        )

        self.client.create_namespaced_pod(namespace=self.namespace, body=service_pod)
        self.client.create_namespaced_service(namespace=self.namespace, body=service_service)

    def write_service_config(self, source_path: str, service_name: str, destination_path: str):
        obj = SERVICES[service_name]
        container_name = "sidecar"
        # Copy the archive from our local drive (Warnet RPC container/pod)
        # to the destination service's sidecar container via ssh
        self.log.info(
            f"Copying local {source_path} to remote {destination_path} for {service_name}"
        )
        subprocess.run(
            [
                "scp",
                "-o",
                "StrictHostKeyChecking=accept-new",
                source_path,
                f"root@{self.get_service_service_name(obj['container_name_suffix'])}.{self.namespace}:/arbitrary_filename.tar",
            ]
        )
        self.log.info(f"Finished copying tarball for {service_name}, unpacking...")
        # Unpack the archive
        stream(
            self.client.connect_get_namespaced_pod_exec,
            self.get_service_pod_name(obj["container_name_suffix"]),
            self.namespace,
            container=container_name,
            command=["/bin/sh", "-c", f"tar -xf /arbitrary_filename.tar -C {destination_path}"],
            stderr=True,
            stdin=False,
            stdout=True,
            tty=False,
            _preload_content=False,
        )
        self.log.info(f"Finished unpacking config data for {service_name} to {destination_path}")
