from .base_service import BaseService


PORT = 3000


class Grafana(BaseService):
    def __init__(self, network_name):
        super().__init__(network_name)
        self.service = {
            "image": "grafana/grafana:latest",
            "container_name": f"{self.network_name}_grafana",
            "ports": [f"3000:{PORT}"],
            "volumes": ["grafana-storage:/var/lib/grafana"],
            "networks": [self.network_name],
        }
