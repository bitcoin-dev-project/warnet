from abc import ABC, abstractmethod
from pathlib import Path


class ContainerInterface(ABC):

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
    def up(self) -> bool:
        """
        Bring an exsiting network that is down, back up.
            e.g. `docker compose -p up -d`
        """
        raise NotImplementedError("This method should be overridden by child class")

    @abstractmethod
    def down(self) -> bool:
        """
        Bring an exsiting network down.
            e.g. `docker compose down`
        """
        raise NotImplementedError("This method should be overridden by child class")

    @abstractmethod
    def get_container(self, container_name: str):
        """
        Get a container handle by [container_name]
        """
        raise NotImplementedError("This method should be overridden by child class")

    @abstractmethod
    def exec_run(self, container_name: str, cmd: str, user: str):
        """
        Exectute a command on a [container_name]
        """
        raise NotImplementedError("This method should be overridden by child class")

    @abstractmethod
    def get_bitcoin_debug_log(self, container_name: str):
        """
        Fetch debug log from container [container_name]
        """
        raise NotImplementedError("This method should be overridden by child class")

    @abstractmethod
    def get_bitcoin_cli(self, container_name: str, method: str, params=None):
        """
        Call `bitcoin-cli` on container [container_name] with [method] and <params>
        """
        raise NotImplementedError("This method should be overridden by child class")

    @abstractmethod
    def get_file(self, container_name: str, file_path: str):
        """
        Read a file from inside a container
        """
        raise NotImplementedError("This method should be overridden by child class")

    @abstractmethod
    def get_messages(self, a_name: str, b_ipv4: str, bitcoin_network: str = "regtest"):
        """
        Get bitcoin messages between containers [a_name] and [b_ipv4] on [bitcoin_network]
        """
        raise NotImplementedError("This method should be overridden by child class")

    @abstractmethod
    def logs_grep(self, pattern: str, network: str):
        """
        Grep logs from all containers matching [pattern] from [network]
        """
        raise NotImplementedError("This method should be overridden by child class")

    @abstractmethod
    def generate_deployment_file(self, warnet):
        """
        Generate a deployment configuration file e.g docker-compose.yml
        Should set warnet.deployment_file
        """
        raise NotImplementedError("This method should be overridden by child class")

    @ abstractmethod
    def warnet_from_deployment(self, warnet):
        """
        Rebuild a warnet object from an active deployment
        """
        raise NotImplementedError("This method should be overridden by child class")

    @abstractmethod
    def tank_from_deployment(self):
        """
        Build a tank object from an active deployment
        """
        raise NotImplementedError("This method should be overridden by child class")

