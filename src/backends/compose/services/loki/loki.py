from ..base_service import BaseService
from pathlib import Path


LOKI_CONF_DIR = Path(__file__).parent
IMAGE = "grafana/loki:2.9.3"
PORT = 3100


class Loki(BaseService):
    def __init__(self, docker_network):
        super().__init__(docker_network)
        self.service = {
            "image": IMAGE,
            "container_name": f"{self.docker_network}-loki",
            "ports": [f"{PORT}:{PORT}"],
            "volumes": [f"{LOKI_CONF_DIR}:/etc/loki"],
            "command": "-config.file=/etc/loki/config.yaml",
            "networks": [self.docker_network],
        }
