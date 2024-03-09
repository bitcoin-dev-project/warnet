import logging
import re
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import cast

import docker
import yaml
from backends import BackendInterface, ServiceType
from cli.image import build_image
from docker.models.containers import Container
from templates import TEMPLATES
from warnet.status import RunningStatus
from warnet.tank import Tank
from warnet.utils import (
    default_bitcoin_conf_args,
    get_architecture,
    parse_raw_messages,
    set_execute_permission,
)

from .services import SERVICES
from .services.cadvisor import CAdvisor
from .services.fork_observer import ForkObserver
from .services.grafana import Grafana
from .services.loki.loki import Loki
from .services.node_exporter import NodeExporter
from .services.prometheus import Prometheus
from .services.promtail.promtail import Promtail
from .services.tor_da import TorDA

DOCKER_COMPOSE_NAME = "docker-compose.yml"
DOCKERFILE_NAME = "Dockerfile"
TORRC_NAME = "torrc.relay"
ENTRYPOINT_NAME = "entrypoint.sh"
DOCKER_REGISTRY = "bitcoindevproject/bitcoin"
LOCAL_REGISTRY = "warnet/bitcoin-core"
GRAFANA_PROVISIONING = "grafana-provisioning"
CONTAINER_PREFIX_BITCOIND = "tank-bitcoin"
CONTAINER_PREFIX_LN = "tank-ln"
CONTAINER_PREFIX_CIRCUITBREAKER = "tank-ln-cb"
LND_MOUNT_PATH = "/root/.lnd"

logger = logging.getLogger("docker-interface")
logging.getLogger("docker.utils.config").setLevel(logging.WARNING)
logging.getLogger("docker.auth").setLevel(logging.WARNING)


class ComposeBackend(BackendInterface):
    def __init__(self, config_dir: Path, network_name: str) -> None:
        super().__init__(config_dir)
        self.network_name = network_name
        self.client: docker.DockerClient = docker.from_env()
        self._apiclient: docker.APIClient = docker.APIClient(base_url="unix://var/run/docker.sock")

    def build(self) -> bool:
        command = ["docker", "compose", "build"]
        try:
            with subprocess.Popen(
                command,
                cwd=str(self.config_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            ) as process:
                logger.debug(f"Running docker compose build with PID {process.pid}")
                if process.stdout:
                    for line in process.stdout:
                        logger.info(line.decode().rstrip())
        except Exception as e:
            logger.error(
                f"An error occurred while executing `{' '.join(command)}` in {self.config_dir}: {e}"
            )
            return False
        return True

    def up(self, *_):
        command = ["docker", "compose", "up", "--detach"]
        try:
            with subprocess.Popen(
                command,
                cwd=str(self.config_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            ) as process:
                logger.debug(f"Running docker compose up --detach with PID {process.pid}")
                if process.stdout:
                    for line in process.stdout:
                        logger.info(line.decode().rstrip())
        except Exception as e:
            logger.error(
                f"An error occurred while executing `{' '.join(command)}` in {self.config_dir}: {e}"
            )

    def down(self, warnet):
        command = ["docker", "compose", "down", "-v"]
        try:
            with subprocess.Popen(
                command,
                cwd=str(self.config_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            ) as process:
                logger.debug(f"Running 'docker compose down -v' with PID {process.pid}")
                if process.stdout:
                    for line in process.stdout:
                        logger.info(line.decode().rstrip())
        except Exception as e:
            logger.error(
                f"An error occurred while executing `{' '.join(command)}` in {self.config_dir}: {e}"
            )

    def get_container_name(self, tank_index: int, service: ServiceType) -> str:
        match service:
            case ServiceType.BITCOIN:
                return f"{self.network_name}-{CONTAINER_PREFIX_BITCOIND}-{tank_index:06}"
            case ServiceType.LIGHTNING:
                return f"{self.network_name}-{CONTAINER_PREFIX_LN}-{tank_index:06}"
            case ServiceType.CIRCUITBREAKER:
                return f"{self.network_name}-{CONTAINER_PREFIX_CIRCUITBREAKER}-{tank_index:06}"
            case _:
                raise Exception("Unsupported service type")

    def get_container(self, tank_index: int, service: ServiceType) -> Container:
        container_name = self.get_container_name(tank_index, service)
        if len(self.client.containers.list(filters={"name": container_name})) == 0:
            return None
        return cast(Container, self.client.containers.get(container_name))

    def tor_ready(self) -> bool:
        container_name = "tor_da"
        if len(self.client.containers.list(filters={"name": container_name})) == 0:
            return False
        container = cast(Container, self.client.containers.get(container_name))
        if container is None:
            return False
        return self.get_container_health(container) == "healthy"


    def get_status(self, tank_index: int, service: ServiceType) -> RunningStatus:
        container = self.get_container(tank_index, service)
        if container is None:
            return RunningStatus.STOPPED
        match container.status:
            case "running":
                return RunningStatus.RUNNING
            case "exited" | "dead":
                if container.attrs["State"]["ExitCode"] == 0:
                    return RunningStatus.STOPPED
                else:
                    return RunningStatus.FAILED
            case _:
                return RunningStatus.PENDING

    def exec_run(self, tank_index: int, service: ServiceType, cmd: str) -> str:
        c = self.get_container(tank_index, service)
        result = c.exec_run(cmd=cmd)
        if result.exit_code != 0:
            raise Exception(
                f"Command failed with exit code {result.exit_code}: {result.output.decode('utf-8')} {cmd}"
            )
        return result.output.decode("utf-8")

    def get_bitcoin_debug_log(self, tank_index: int):
        container_name = self.get_container_name(tank_index, ServiceType.BITCOIN)
        now = datetime.utcnow()

        logs = self.client.api.logs(
            container=container_name,
            stdout=True,
            stderr=True,
            stream=False,  # return a string
            until=now,
        )
        return cast(bytes, logs).decode("utf8")  # cast for typechecker

    def ln_cli(self, tank: Tank, command: list[str]):
        if tank.lnnode is None:
            raise Exception("No LN node configured for tank")
        cmd = tank.lnnode.generate_cli_command(command)
        return self.exec_run(tank.index, ServiceType.LIGHTNING, cmd)

    def get_bitcoin_cli(self, tank: Tank, method: str, params=None):
        if params:
            cmd = f"bitcoin-cli -regtest -rpcuser={tank.rpc_user} -rpcport={tank.rpc_port} -rpcpassword={tank.rpc_password} {method} {' '.join(map(str, params))}"
        else:
            cmd = f"bitcoin-cli -regtest -rpcuser={tank.rpc_user} -rpcport={tank.rpc_port} -rpcpassword={tank.rpc_password} {method}"
        return self.exec_run(tank.index, ServiceType.BITCOIN, cmd)

    def get_file(self, tank_index: int, service: ServiceType, file_path: str):
        container = self.get_container(tank_index, service)
        data, stat = container.get_archive(file_path)
        out = b""
        for chunk in data:
            out += chunk
        # slice off tar archive header
        out = out[512:]
        # slice off end padding
        out = out[: stat["size"]]
        return out

    def get_tank_ipv4(self, index: int) -> str:
        c = self.get_container(index, ServiceType.BITCOIN)
        if c:
            return self.get_ipv4_address(c)
        else:
            return None

    def get_messages(self, a_index: int, b_index: int, bitcoin_network: str = "regtest"):
        # Find the ip of peer B
        b_ipv4 = self.get_tank_ipv4(b_index)

        # find the corresponding message capture folder
        # (which may include the internal port if connection is inbound)
        subdir = "/" if bitcoin_network == "main" else f"{bitcoin_network}/"
        base_dir = f"/root/.bitcoin/{subdir}message_capture"
        dirs = self.exec_run(a_index, ServiceType.BITCOIN, f"ls {base_dir}")
        dirs = dirs.splitlines()
        messages = []
        for dir_name in dirs:
            if b_ipv4 in dir_name:
                for file, outbound in [["msgs_recv.dat", False], ["msgs_sent.dat", True]]:
                    blob = self.get_file(
                        a_index,
                        ServiceType.BITCOIN,
                        f"{base_dir}/{dir_name}/{file}",
                    )
                    json = parse_raw_messages(blob, outbound)
                    messages = messages + json
        messages.sort(key=lambda x: x["time"])
        return messages

    def get_containers_in_network(self, network: str) -> list[str]:
        # Return list of container names in the specified network
        containers = []
        for container in self.client.containers.list(filters={"network": network}):
            containers.append(container.name)
        logger.debug(f"Got containers: {containers}")
        return containers

    def logs_grep(self, pattern: str, network: str) -> str:
        compiled_pattern = re.compile(pattern)
        containers = self.get_containers_in_network(network)

        all_matching_logs: list[tuple[str, str]] = []

        for container_name in containers:
            logger.debug(f"Fetching logs from {container_name}")
            logs = self.client.api.logs(
                container=container_name,
                stdout=True,
                stderr=True,
                stream=False,
            )
            logs = logs.decode("utf-8").splitlines()

            for log_entry in logs:
                log_entry_str = log_entry.strip()
                if compiled_pattern.search(log_entry_str):
                    all_matching_logs.append((container_name, log_entry_str))

        # Sort by timestamp; Python's default tuple sorting will sort by the second element, which is the timestamp
        all_matching_logs.sort(key=lambda x: x[1])

        # Format and join the sorted logs
        sorted_logs = [f"{container} {log}" for container, log in all_matching_logs]

        return "\n".join(sorted_logs)

    def write_prometheus_config(self, warnet):
        scrape_configs = [
            {
                "job_name": "cadvisor",
                "scrape_interval": "15s",
                "static_configs": [{"targets": [f"{warnet.network_name}_cadvisor:8080"]}],
            }
        ]

        for tank in warnet.tanks:
            if tank.exporter:
                scrape_configs.append(
                    {
                        "job_name": tank.exporter_name,
                        "scrape_interval": "5s",
                        "static_configs": [{"targets": [f"{tank.exporter_name}:9332"]}],
                    }
                )

        config = {"global": {"scrape_interval": "15s"}, "scrape_configs": scrape_configs}

        prometheus_path = self.config_dir / "prometheus.yml"
        try:
            with open(prometheus_path, "w") as file:
                yaml.dump(config, file)
            logger.info(f"Wrote file: {prometheus_path}")
        except Exception as e:
            logger.error(f"An error occurred while writing to {prometheus_path}: {e}")

    def _write_docker_compose(self, warnet):
        compose = {
            "version": "3.8",
            "name": "warnet",
            "networks": {
                warnet.network_name: {
                    "name": warnet.network_name,
                    "ipam": {"config": [{"subnet": warnet.subnet}]},
                }
            },
            "volumes": {"grafana-storage": None},
            "services": {},
        }

        # Pass services object to each tank so they can add whatever they need.
        for tank in warnet.tanks:
            self.add_services(tank, compose)

        # Initialize services and add them to the compose
        services = [
            Prometheus(warnet.network_name, self.config_dir),
            NodeExporter(warnet.network_name),
            Grafana(warnet.network_name),
            CAdvisor(warnet.network_name, TEMPLATES),
            ForkObserver(warnet.network_name, warnet.fork_observer_config),
            Loki(warnet.network_name),
            Promtail(warnet.network_name),
        ]

        if warnet.tor:
            services.append(TorDA(warnet.network_name))

        for service_obj in services:
            service_name = service_obj.__class__.__name__.lower()
            compose["services"][service_name] = service_obj.get_service()

        docker_compose_path = warnet.config_dir / "docker-compose.yml"
        try:
            with open(docker_compose_path, "w") as file:
                yaml.dump(compose, file)
            logger.info(f"Wrote file: {docker_compose_path}")
        except Exception as e:
            logger.error(f"An error occurred while writing to {docker_compose_path}: {e}")

    def generate_deployment_file(self, warnet):
        self._write_docker_compose(warnet)
        self.write_prometheus_config(warnet)
        warnet.deployment_file = warnet.config_dir / DOCKER_COMPOSE_NAME
        logger.debug(f"{SERVICES=}")
        logger.debug(f"{SERVICES / GRAFANA_PROVISIONING=}")
        logger.debug(f"{self.config_dir=}")
        shutil.copytree(
            SERVICES / GRAFANA_PROVISIONING,
            self.config_dir / GRAFANA_PROVISIONING,
            dirs_exist_ok=True,
        )

    def config_args(self, tank: Tank):
        args = self.default_config_args(tank)
        if tank.bitcoin_config is not None:
            args = f"{args} -{tank.bitcoin_config.replace(',', ' -')}"
        return args

    def default_config_args(self, tank):
        defaults = default_bitcoin_conf_args()
        defaults += f" -rpcuser={tank.rpc_user}"
        defaults += f" -rpcpassword={tank.rpc_password}"
        defaults += f" -rpcport={tank.rpc_port}"
        defaults += f" -zmqpubrawblock=tcp://0.0.0.0:{tank.zmqblockport}"
        defaults += f" -zmqpubrawtx=tcp://0.0.0.0:{tank.zmqtxport}"
        # connect to initial peers as defined in graph file
        for dst_index in tank.init_peers:
            defaults += f" -addnode={self.get_container_name(dst_index, ServiceType.BITCOIN)}"
        return defaults

    def copy_configs(self, tank):
        warnet_tor_dir = tank.config_dir / "tor"
        warnet_tor_dir.mkdir()
        shutil.copyfile(TEMPLATES / DOCKERFILE_NAME, tank.config_dir / DOCKERFILE_NAME)
        shutil.copyfile(TEMPLATES / "tor" / TORRC_NAME, warnet_tor_dir / "torrc")
        shutil.copyfile(TEMPLATES / ENTRYPOINT_NAME, tank.config_dir / ENTRYPOINT_NAME)
        set_execute_permission(tank.config_dir / ENTRYPOINT_NAME)

    def add_services(self, tank: Tank, compose):
        services = compose["services"]
        assert tank.index is not None
        container_name = self.get_container_name(tank.index, ServiceType.BITCOIN)
        services[container_name] = {}

        # Setup bitcoind, either release binary, pre-built image or built from source on demand
        if tank.version and ("/" and "#" in tank.version):
            # it's a git branch, building step is necessary
            repo, branch = tank.version.split("#")
            services[container_name]["image"] = f"{LOCAL_REGISTRY}:{branch}"
            build_image(
                repo,
                branch,
                LOCAL_REGISTRY,
                branch,
                tank.DEFAULT_BUILD_ARGS + tank.build_args,
                arches=get_architecture(),
            )
            self.copy_configs(tank)
        elif tank.image:
            # Pre-built custom image
            image = tank.image
            services[container_name]["image"] = image
        else:
            # Pre-built regular release
            image = f"{DOCKER_REGISTRY}:{tank.version}"
            services[container_name]["image"] = image

        environment =  {
            "BITCOIN_ARGS": self.config_args(tank)
        }
        if tank.tor:
            # Tor DA required in the network to be usable by tank
            assert tank.warnet.tor
            environment["TOR"] = "1"

        # Add common bitcoind service details
        services[container_name].update(
            {
                "container_name": container_name,
                # logging with json-file to support log shipping with promtail into loki
                "logging": {"driver": "json-file", "options": {"max-size": "10m"}},
                "environment": environment,
                "networks": {
                    tank.network_name: {
                        "ipv4_address": f"{tank.ipv4}",
                    }
                },
                "labels": {"warnet": "tank"},
                "privileged": True,
                "cap_add": ["NET_ADMIN", "NET_RAW"],
                "healthcheck": {
                    "test": ["CMD-SHELL", f"nc -z localhost {tank.rpc_port} || exit 1"],
                    "interval": "10s",  # Check every 10 seconds
                    "timeout": "1s",  # Give the check 1 second to complete
                    "start_period": "5s",  # Start checking after 5 seconds
                    "retries": 3,
                },
            }
        )

        if tank.collect_logs:
            services[container_name]["labels"].update({"collect_logs": True})

        if tank.lnnode is not None:
            self.add_lnd_service(tank, compose)

        # Add the prometheus data exporter in a neighboring container
        if tank.exporter:
            services[tank.exporter_name] = {
                "image": "jvstein/bitcoin-prometheus-exporter:latest",
                "container_name": tank.exporter_name,
                "environment": {
                    "BITCOIN_RPC_HOST": tank.ipv4,
                    "BITCOIN_RPC_PORT": tank.rpc_port,
                    "BITCOIN_RPC_USER": tank.rpc_user,
                    "BITCOIN_RPC_PASSWORD": tank.rpc_password,
                },
                "networks": [tank.network_name],
            }

    def add_lnd_service(self, tank, compose):
        services = compose["services"]
        ln_container_name = self.get_container_name(tank.index, ServiceType.LIGHTNING)
        ln_cb_container_name = self.get_container_name(tank.index, ServiceType.CIRCUITBREAKER)
        bitcoin_container_name = self.get_container_name(tank.index, ServiceType.BITCOIN)
        # These args are appended to the Dockerfile `ENTRYPOINT ["lnd"]`
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
            f"--bitcoind.rpchost={tank.ipv4}:{tank.rpc_port}",
            f"--bitcoind.zmqpubrawblock=tcp://{tank.ipv4}:{tank.zmqblockport}",
            f"--bitcoind.zmqpubrawtx=tcp://{tank.ipv4}:{tank.zmqtxport}",
            f"--externalip={tank.lnnode.ipv4}",
            f"--rpclisten=0.0.0.0:{tank.lnnode.rpc_port}",
            f"--alias={tank.index}",
            f"--tlsextradomain={ln_container_name}",
        ]
        services[ln_container_name] = {
            "container_name": ln_container_name,
            "image": tank.lnnode.image,
            "command": " ".join(args),
            "networks": {
                tank.network_name: {
                    "ipv4_address": f"{tank.lnnode.ipv4}",
                }
            },
            "labels": {
                "tank_index": tank.index,
                "tank_container_name": bitcoin_container_name,
                "tank_ipv4_address": tank.ipv4,
            },
            "depends_on": {bitcoin_container_name: {"condition": "service_healthy"}},
            "restart": "on-failure",
        }
        services[bitcoin_container_name].update(
            {
                "labels": {
                    "lnnode_container_name": ln_container_name,
                    "lnnode_ipv4_address": tank.lnnode.ipv4,
                    "lnnode_impl": tank.lnnode.impl,
                    "lnnode_image": tank.lnnode.image,
                }
            }
        )
        if tank.collect_logs:
            services[ln_container_name]["labels"].update({"collect_logs": True})
        if tank.lnnode.cb is not None:
            services[ln_container_name].update(
                {"volumes": [f"{ln_container_name}-data:{LND_MOUNT_PATH}"]}
            )
            services[ln_cb_container_name] = {
                "container_name": ln_cb_container_name,
                "image": tank.lnnode.cb,
                "volumes": [f"{ln_container_name}-data:{LND_MOUNT_PATH}"],
                "command": "--network=regtest "
                + f"--rpcserver={ln_container_name}:{tank.lnnode.rpc_port} "
                + f" --tlscertpath={LND_MOUNT_PATH}/tls.cert "
                + f" --macaroonpath={LND_MOUNT_PATH}/data/chain/bitcoin/regtest/admin.macaroon",
                "networks": [tank.network_name],
                "restart": "on-failure",
            }
            compose["volumes"].update({f"{ln_container_name}-data": None})

    def get_ipv4_address(self, container: Container) -> str:
        """
        Fetches the IPv4 address of a given container.
        """
        container_inspect = self.client.containers.get(container.id).attrs
        return container_inspect["NetworkSettings"]["Networks"][self.network_name]["IPAddress"]

    def get_container_health(self, container: Container):
        c_inspect = self._apiclient.inspect_container(container.name)
        return c_inspect["State"]["Health"]["Status"]

    def check_health_all_bitcoind(self, warnet) -> bool:
        """
        Checks the health of all bitcoind containers
        """
        status = ["unhealthy"] * len(warnet.tanks)

        for tank in warnet.tanks:
            status[tank.index] = self.get_container_health(
                self.get_container(tank.index, ServiceType.BITCOIN)
            )
        logger.debug(f"Tank healthcheck: {status}")

        return status[0] == "healthy" and all(i == status[0] for i in status)

    def wait_for_healthy_tanks(self, warnet, timeout=60) -> bool:
        start = time.time()
        healthy = False
        logger.debug("Waiting for all tanks to reach healthy")

        while not healthy and (time.time() < start + timeout):
            healthy = self.check_health_all_bitcoind(warnet)
            time.sleep(2)

        if not healthy:
            raise Exception(f"Tanks did not reach healthy status in {timeout} seconds")

        return healthy
