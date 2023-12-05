from .base_service import BaseService

PORT = 12323


class ForkObserver(BaseService):
    def __init__(self, docker_network, fork_observer_config):
        super().__init__(docker_network)
        self.fork_observer_config = fork_observer_config
        self.service = {
            "image": "b10c/fork-observer:latest",
            "container_name": f"{self.docker_network}-fork-observer",
            "ports": [f"{PORT}:2323"],
            "volumes": [f"{self.fork_observer_config}:/app/config.toml"],
            "networks": [self.docker_network],
        }
