from .base_service import BaseService

PORT = 8080
VERSION = "v0.47.2"


class CAdvisor(BaseService):
    def __init__(self, docker_network, config_dir):
        super().__init__(docker_network, config_dir)
        self.service = {
            "image": f"gcr.io/cadvisor/cadvisor:{VERSION}",
            "container_name": f"{self.docker_network}_cadvisor",
            "ports": [f"{PORT}:8080"],
            "volumes": [
                f"/:/rootfs:ro",
                f"/var/run:/var/run:ro",
                f"/sys:/sys:ro",
                f"/var/lib/docker/:/var/lib/docker:ro",
                f"/dev/disk/:/dev/disk:ro",
            ],
            "networks": [self.docker_network],
            "privileged": True,
            "devices": ["/dev/kmsg"]
        }

