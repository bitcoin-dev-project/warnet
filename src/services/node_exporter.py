from .base_service import BaseService


class NodeExporter(BaseService):
    def __init__(self, network_name):
        super().__init__(network_name)
        self.service = {
            "image": "prom/node-exporter:latest",
            "container_name": f"{self.network_name}_node-exporter",
            "volumes": ["/proc:/host/proc:ro", "/sys:/host/sys:ro", "/:/rootfs:ro"],
            "command": ["--path.procfs=/host/proc", "--path.sysfs=/host/sys"],
            "networks": [self.network_name],
        }
