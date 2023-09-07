from .base_service import BaseService
import shutil


IP_ADDR = "100.1.1.1"
PORT = 15353
DNS_SEED_NAME = "dns-seed"
ZONE_FILE_NAME = "invalid.zone"
NAMED_CONF_NAME = "named.conf.local"


class DnsSeed(BaseService):
    def __init__(self, docker_network, templates, config_dir):
        super().__init__(docker_network)
        self.docker_network = docker_network
        self.templates = templates
        self.service = {
            "container_name": f"{self.docker_network}_{DNS_SEED_NAME}",
            "ports": [f"{PORT}:53/udp", f"{PORT}:53/tcp"],
            "build": {
                "context": ".",
                "dockerfile": str(self.templates / "Dockerfile_bind9"),
            },
            "networks": {
                self.docker_network: {
                    "ipv4_address": f"{IP_ADDR}",
                }
            },
        }
        # Copy files for dockerfile
        shutil.copy(str(self.templates / ZONE_FILE_NAME), config_dir)
        shutil.copy(str(self.templates / NAMED_CONF_NAME), config_dir)
