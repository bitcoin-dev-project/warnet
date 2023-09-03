from pathlib import Path


class BaseService:
    def __init__(self, docker_network, config_dir=Path()):
        self.docker_network = docker_network
        self.config_dir = config_dir
        self.service = {}

    def get_service(self):
        return self.service
