from .base_service import BaseService

PORT = 3000


class Grafana(BaseService):
    def __init__(self, docker_network):
        super().__init__(docker_network)
        self.service = {
            "image": "grafana/grafana:latest",
            "container_name": f"{self.docker_network}_grafana",
            "ports": [f"3000:{PORT}"],
            "volumes": [
                "grafana-storage:/var/lib/grafana",
                f"{self.config_dir}/grafana-provisioning/datasources:/etc/grafana/provisioning/datasources",
                f"{self.config_dir}/grafana-provisioning/dashboards:/etc/grafana/provisioning/dashboards",
            ],
            "networks": [self.docker_network],
            "environment": ["GF_LOG_LEVEL=debug"],
        }
