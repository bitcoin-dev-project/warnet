from abc import ABC, abstractmethod
from pathlib import Path


class BaseService(ABC):
    def __init__(self, network_name, config_dir=Path()):
        self.network_name = network_name
        self.config_dir = config_dir
        self.name = ""

    @abstractmethod
    def add_to_deployment(self):
        """
        Add the service to the deployment
        """
        raise NotImplementedError("This method should be overridden by child class")
