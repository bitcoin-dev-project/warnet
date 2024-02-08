from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path


class ServiceType(Enum):
    BITCOIN = 1
    LIGHTNING = 2


class BackendInterface(ABC):
    def __init__(self, config_dir: Path) -> None:
        self.config_dir = config_dir
        self.client = None

    @abstractmethod
    def build(self) -> bool:
        """
        Build a network
            e.g. `docker compose build`
        """
        raise NotImplementedError("This method should be overridden by child class")

    @abstractmethod
    def up(self, warnet) -> bool:
        """
        Bring an exsiting network that is down, back up.
            e.g. `docker compose -p up -d`
        """
        raise NotImplementedError("This method should be overridden by child class")

    @abstractmethod
    def down(self, warnet) -> bool:
        """
        Bring an exsiting network down.
            e.g. `docker compose down`
        """
        raise NotImplementedError("This method should be overridden by child class")

    @abstractmethod
    def get_status(self, tank_index: int, service: ServiceType):
        """
        Get the running status of a tank by [tanks_index]
        """
        raise NotImplementedError("This method should be overridden by child class")

    @abstractmethod
    def exec_run(self, tank_index: int, service: ServiceType, cmd: str):
        """
        Exectute a command on tank [tank_index] in service [service]
        """
        raise NotImplementedError("This method should be overridden by child class")

    @abstractmethod
    def get_bitcoin_debug_log(self, tank_index: int):
        """
        Fetch debug log from tank [tank_index]
        """
        raise NotImplementedError("This method should be overridden by child class")

    @abstractmethod
    def ln_cli(self, tank, command: list[str]) -> str:
        """
        Call `lightning cli` on tank [tank_index] with <command>
        """
        raise NotImplementedError("This method should be overridden by child class")

    @abstractmethod
    def get_bitcoin_cli(self, tank, method: str, params=None):
        """
        Call `bitcoin-cli` on tank [tank_index] with [method] and <params>
        """
        raise NotImplementedError("This method should be overridden by child class")

    @abstractmethod
    def get_file(self, tank_index: int, service: ServiceType, file_path: str):
        """
        Read a file from inside a container
        """
        raise NotImplementedError("This method should be overridden by child class")

    @abstractmethod
    def get_messages(self, tank_index: int, b_ipv4: str, bitcoin_network: str = "regtest"):
        """
        Get bitcoin messages between containers [tank_index] and [b_ipv4] on [bitcoin_network]
        """
        raise NotImplementedError("This method should be overridden by child class")

    @abstractmethod
    def logs_grep(self, pattern: str, network: str):
        """
        Grep logs from all containers matching [pattern] from [network]
        """
        raise NotImplementedError("This method should be overridden by child class")

    @abstractmethod
    def generate_deployment_file(self, warnet) -> None:
        """
        Generate a deployment configuration file e.g docker-compose.yml
        Should set warnet.deployment_file
        """
        raise NotImplementedError("This method should be overridden by child class")

    @abstractmethod
    def warnet_from_deployment(self, warnet):
        """
        Rebuild a warnet object from an active deployment
        """
        raise NotImplementedError("This method should be overridden by child class")
