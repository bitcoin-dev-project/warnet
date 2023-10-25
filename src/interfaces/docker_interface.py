import logging
import re
import shlex
import shutil
import subprocess
import yaml

from copy import deepcopy
from pathlib import Path
from typing import cast, Optional, List
import docker
from docker.models.containers import Container

from .interfaces import ContainerInterface
from warnet.utils import bubble_exception_str, parse_raw_messages
from services.tor import Tor
from services.fork_observer import ForkObserver
from services.fluentd import Fluentd
from templates import TEMPLATES
from warnet.tank import Tank, CONTAINER_PREFIX_BITCOIND
from warnet.utils import bubble_exception_str, parse_raw_messages, parse_bitcoin_conf, dump_bitcoin_conf, get_architecture, set_execute_permission


DOCKER_COMPOSE_NAME = "docker-compose.yml"
DOCKERFILE_NAME = "Dockerfile"
TORRC_NAME = "torrc"
WARNET_ENTRYPOINT_NAME = "warnet_entrypoint.sh"
DOCKER_ENTRYPOINT_NAME = "docker_entrypoint.sh"

logger = logging.getLogger("docker-interface")
logging.getLogger("docker.utils.config").setLevel(logging.WARNING)
logging.getLogger("docker.auth").setLevel(logging.WARNING)


def run_subprocess(command: str, config_dir: Path, ret_val: Optional[List[str]] = None) -> bool:
    args = shlex.split(command)
    try:
        with subprocess.Popen(
            args,
            cwd=str(config_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        ) as process:
            logger.debug(f"Running {command} with PID {process.pid}")
            if process.stdout:
                for line in process.stdout:
                    decoded_line = line.decode().strip()
                    if ret_val is not None:
                        ret_val.append(decoded_line)
                    else:
                        logger.info(decoded_line)
    except Exception as e:
        logger.error(
            f"An error occurred while executing `{' '.join(args)}` in {config_dir}: {e}"
        )
        return False
    return True


class DockerInterface(ContainerInterface):
    def __init__(self, network: str, config_dir: Path) -> None:
        super().__init__(network, config_dir)
        self.client = docker.DockerClient = docker.from_env()

    @bubble_exception_str
    def build(self) -> bool:
        command = "docker compose build"
        return run_subprocess(command, self.config_dir)


    @bubble_exception_str
    def up(self):
        command = "docker compose up --detach"
        return run_subprocess(command, self.config_dir)

    @bubble_exception_str
    def down(self):
        command = "docker compose down"
        return run_subprocess(command, self.config_dir)

    def get_container(self, container_name: str) -> Container:
        return cast(Container, self.client.containers.get(container_name))

    def exec_run(self, container_name: str, cmd: str, user: str = "root") -> str:
        command = f"docker exec -it {container_name} gosu {user} {cmd}"
        result = []
        run_subprocess(command, self.config_dir, result)
        return "\n".join(result)

    def get_bitcoin_debug_log(self, container_name: str):
        # TODO: technically this is all docker logs, but I think that's ok
        command = f"docker logs {container_name}"
        result = []
        run_subprocess(command, self.config_dir, result)
        return "\n".join(result)

    def get_bitcoin_cli(self, container_name: str, method: str, params=None):
        if params:
            cmd = f"bitcoin-cli {method} {' '.join(map(str, params))}"
        else:
            cmd = f"bitcoin-cli {method}"
        return self.exec_run(container_name, cmd, user="bitcoin")

    def get_messages(self, a_name: str, b_ipv4: str, bitcoin_network: str = "regtest"):
        src_node = self.get_container(a_name)
        # start with the IP of the peer
        # find the corresponding message capture folder
        # (which may include the internal port if connection is inbound)
        subdir = (
            "/" if bitcoin_network == "main" else f"{bitcoin_network}/"
        )
        dirs = self.exec_run(a_name, f"ls /home/bitcoin/.bitcoin/{subdir}message_capture")
        dirs = dirs.splitlines()
        messages = []
        for dir_name in dirs:
            if b_ipv4 in dir_name:
                for file, outbound in [["msgs_recv.dat", False], ["msgs_sent.dat", True]]:
                    data, stat = src_node.get_archive(
                        f"/home/bitcoin/.bitcoin/{subdir}message_capture/{dir_name}/{file}"
                    )
                    blob = b""
                    for chunk in data:
                        blob += chunk
                    # slice off tar archive header
                    blob = blob[512:]
                    # slice off end padding
                    blob = blob[: stat["size"]]
                    # parse
                    json = parse_raw_messages(blob, outbound)
                    messages = messages + json
        messages.sort(key=lambda x: x["time"])
        return messages

    def logs_grep(self, pattern: str, container_name: str) -> str:
        compiled_pattern = re.compile(pattern)
        command = f"docker logs {container_name}"
        args = shlex.split(command)
        matching_logs = []

        try:
            with subprocess.Popen(
                    args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
            ) as process:
                logger.debug(f"Running {command} with PID {process.pid}")
                if process.stdout:
                    for line in iter(process.stdout.readline, b''):
                        decoded_line = line.decode().rstrip()
                        if compiled_pattern.search(decoded_line):
                            matching_logs.append(decoded_line)
        except Exception as e:
            logger.error(
                f"An error occurred while executing `{' '.join(args)}`: {e}"
            )
        return '\n'.join(matching_logs)

    def _write_bitcoin_confs(self, warnet):
        with open(TEMPLATES / "bitcoin.conf", "r") as file:
            text = file.read()
        base_bitcoin_conf = parse_bitcoin_conf(text)
        for tank in warnet.tanks:
            self.write_bitcoin_conf(tank,base_bitcoin_conf)

    def _write_docker_compose(self, warnet):
        compose = {
            "version": "3.8",
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
            self.add_services(tank, compose["services"])

        # Initialize services and add them to the compose
        services = [
            # grep: disable-exporters
            # Prometheus(self.network_name, self.config_dir),
            # NodeExporter(self.network_name),
            # Grafana(self.network_name),
            Tor(warnet.network_name, TEMPLATES),
            ForkObserver(warnet.network_name, warnet.fork_observer_config),
            Fluentd(warnet.network_name, warnet.config_dir),
        ]

        for service_obj in services:
            service_name = service_obj.__class__.__name__.lower()
            compose["services"][service_name] = service_obj.get_service()

        docker_compose_path = warnet.config_dir / "docker-compose.yml"
        try:
            with open(docker_compose_path, "w") as file:
                yaml.dump(compose, file)
            logger.info(f"Wrote file: {docker_compose_path}")
        except Exception as e:
            logger.error(
                f"An error occurred while writing to {docker_compose_path}: {e}"
            )

    def generate_deployment_file(self, warnet):
        self._write_bitcoin_confs(warnet)
        self._write_docker_compose(warnet)
        warnet.deployment_file = warnet.config_dir / DOCKER_COMPOSE_NAME


    def write_bitcoin_conf(self, tank, base_bitcoin_conf):
        conf = deepcopy(base_bitcoin_conf)
        options = tank.conf.split(",")
        for option in options:
            option = option.strip()
            if option:
                if "=" in option:
                    key, value = option.split("=")
                else:
                    key, value = option, "1"
                conf[tank.bitcoin_network].append((key, value))

        conf[tank.bitcoin_network].append(("rpcuser", tank.rpc_user))
        conf[tank.bitcoin_network].append(("rpcpassword", tank.rpc_password))
        conf[tank.bitcoin_network].append(("rpcport", tank.rpc_port))

        conf_file = dump_bitcoin_conf(conf)
        path = tank.config_dir / f"bitcoin.conf"
        logger.info(f"Wrote file {path}")
        with open(path, "w") as file:
            file.write(conf_file)
        tank.conf_file = path

    def copy_torrc(self, tank):
        shutil.copyfile(Path(TEMPLATES) / TORRC_NAME, tank.config_dir/ TORRC_NAME)

    def copy_entrypoints(self, tank):
        shutil.copyfile(Path(TEMPLATES) / WARNET_ENTRYPOINT_NAME, tank.config_dir / WARNET_ENTRYPOINT_NAME)
        set_execute_permission(tank.config_dir / WARNET_ENTRYPOINT_NAME)

        shutil.copyfile(Path(TEMPLATES) / DOCKER_ENTRYPOINT_NAME, tank.config_dir / DOCKER_ENTRYPOINT_NAME)
        set_execute_permission(tank.config_dir / DOCKER_ENTRYPOINT_NAME)

    def copy_dockerfile(self, tank):
        shutil.copyfile(Path(TEMPLATES) / DOCKERFILE_NAME, tank.config_dir / DOCKERFILE_NAME)

    def copy_configs(self, tank):
        self.copy_torrc(tank)
        self.copy_entrypoints(tank)
        self.copy_dockerfile(tank)

    def add_services(self, tank, services):
        assert tank.index is not None
        assert tank.conf_file is not None
        services[tank.container_name] = {}

        self.copy_configs(tank)

        # Setup bitcoind, either release binary or build from source
        if "/" and "#" in tank.version:
            # it's a git branch, building step is necessary
            repo, branch = tank.version.split("#")
            build = {
                "context": str(tank.config_dir),
                "dockerfile": str(tank.config_dir / DOCKERFILE_NAME),
                "args": {
                    "REPO": repo,
                    "BRANCH": branch,
                    "BUILD_ARGS": f"{tank.DEFAULT_BUILD_ARGS + tank.extra_build_args}",
                },
            }
        else:
            # assume it's a release version, get the binary
            build = {
                "context": str(tank.config_dir),
                "dockerfile": str(tank.config_dir / DOCKERFILE_NAME),
                "args": {
                    "ARCH": get_architecture(),
                    "BITCOIN_URL": "https://bitcoincore.org/bin",
                    "BITCOIN_VERSION": f"{tank.version}",
                },
            }
        # Add the bitcoind service
        services[tank.container_name].update(
            {
                "container_name": tank.container_name,
                "build": build,
                "networks": {
                    tank.network_name: {
                        "ipv4_address": f"{tank.ipv4}",
                    }
                },
                "labels": {"warnet": "tank"},
                "privileged": True,
                "cap_add": ["NET_ADMIN", "NET_RAW"],
                "depends_on": {
                    "fluentd": {
                        "condition": "service_healthy"
                    }
                },
                "healthcheck": {
                    "test": ["CMD", "pidof", "bitcoind"],
                    "interval": "30s",            # Check every 30 seconds
                    "timeout": "1s",             # Give the check 1 second to complete
                    "start_period": "5s",       # Start checking after 5 seconds
                    "retries": 3
                },
                "logging": {
                    "driver": "fluentd",
                    "options": {
                        "tag": "{{.Name}}"
                    }
                }
            }
        )

        # grep: disable-exporters
        # Add the prometheus data exporter in a neighboring container
        # services[self.exporter_name] = {
        #     "image": "jvstein/bitcoin-prometheus-exporter",
        #     "container_name": self.exporter_name,
        #     "environment": {
        #         "BITCOIN_RPC_HOST": self.container_name,
        #         "BITCOIN_RPC_PORT": self.rpc_port,
        #         "BITCOIN_RPC_USER": self.rpc_user,
        #         "BITCOIN_RPC_PASSWORD": self.rpc_password,
        #     },
        #     "ports": [f"{8335 + self.index}:9332"],
        #     "networks": [self.docker_network],
        # }

    # def add_scrapers(self, scrapers):
    #     scrapers.append(
    #         {
    #             "job_name": self.container_name,
    #             "scrape_interval": "5s",
    #             "static_configs": [{"targets": [f"{self.exporter_name}:9332"]}],
    #         }
    #     )

    def warnet_from_deployment(self, warnet):
        # Get tank names, versions and IP addresses from docker-compose
        docker_compose_path = warnet.config_dir / DOCKER_COMPOSE_NAME
        compose = None
        with open(docker_compose_path, "r") as file:
            compose = yaml.safe_load(file)
        for service_name in compose["services"]:
            tank = self.tank_from_deployment(compose["services"][service_name], warnet)
            if tank is not None:
                warnet.tanks.append(tank)

    def tank_from_deployment(self, service, warnet):
        rex = fr"{warnet.network_name}_{CONTAINER_PREFIX_BITCOIND}_([0-9]{{6}})"
        match = re.match(rex, service["container_name"])
        if match is None:
            return None

        index = int(match.group(1))
        t = Tank(index, warnet.config_dir, warnet)
        t._ipv4 = service["networks"][t.network_name]["ipv4_address"]
        if "BITCOIN_VERSION" in service["build"]["args"]:
            t.version = service["build"]["args"]["BITCOIN_VERSION"]
        else:
            t.version = f"{service['build']['args']['REPO']}#{service['build']['args']['BRANCH']}"
        return t

