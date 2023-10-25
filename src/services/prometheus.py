from .base_service import BaseService


PORT = 9090


class Prometheus(BaseService):
    def __init__(self, network_name, config_dir):
        super().__init__(network_name, config_dir)
        self.service = {
            "image": "prom/prometheus:latest",
            "container_name": f"{self.network_name}_prometheus",
            "ports": [f"{PORT}:9090"],
            "volumes": [
                f"{self.config_dir / 'prometheus.yml'}:/etc/prometheus/prometheus.yml"
            ],
            "command": ["--config.file=/etc/prometheus/prometheus.yml"],
            "networks": [self.network_name],
        }
