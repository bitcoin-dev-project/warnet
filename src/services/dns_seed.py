from .base_service import BaseService
import shutil


PORT = 15353


class DnsSeed(BaseService):
    def __init__(self, docker_network, templates, config_dir):
        super().__init__(docker_network)
        self.docker_network = docker_network
        self.templates = templates
        self.service = {
            "container_name": "dns-seed",
            "ports": [f"{PORT}:53/udp", f"{PORT}:53/tcp"],
            "build": {
                "context": ".",
                "dockerfile": str(self.templates / "Dockerfile_bind9"),
            },
            "networks": [self.docker_network],
        }
        # Copy files for dockerfile
        shutil.copy(str(self.templates / "dns-seed.zone"), config_dir)
        shutil.copy(str(self.templates / "named.conf.local"), config_dir)
