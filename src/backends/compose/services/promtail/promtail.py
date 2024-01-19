from ..base_service import BaseService
from pathlib import Path


PROMTAIL_CONF_DIR = Path(__file__).parent
IMAGE = "grafana/promtail:2.9.3"


class Promtail(BaseService):
    def __init__(self, docker_network):
        super().__init__(docker_network)
        self.service = {
            "image": IMAGE,
            "container_name": f"{self.docker_network}-promtail",
            "volumes": [
                f"{PROMTAIL_CONF_DIR}:/etc/promtail",
                # to read container labels and logs
                "/var/run/docker.sock:/var/run/docker.sock",
                "/var/lib/docker/containers:/var/lib/docker/containers",
            ],
            "command": "-config.file=/etc/promtail/config.yaml",
            "networks": [self.docker_network],
        }
