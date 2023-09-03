from .base_service import BaseService

PORT = 3000


class Grafana(BaseService):
    def __init__(self, docker_network):
        super().__init__(docker_network)
        self.service = {
            "image": "grafana/grafana:latest",
            "container_name": "grafana",
            "ports": [f"3000:{PORT}"],
            "volumes": ["grafana-storage:/var/lib/grafana"],
            "networks": [self.docker_network],
        }
