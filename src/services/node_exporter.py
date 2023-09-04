from .base_service import BaseService


class NodeExporter(BaseService):
    def __init__(self, docker_network):
        super().__init__(docker_network)
        self.service = {
            "image": "prom/node-exporter:latest",
            "container_name": f"{self.docker_network}_node-exporter",
            "volumes": ["/proc:/host/proc:ro", "/sys:/host/sys:ro", "/:/rootfs:ro"],
            "command": ["--path.procfs=/host/proc", "--path.sysfs=/host/sys"],
            "networks": [self.docker_network],
        }
