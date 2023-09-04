from .base_service import BaseService

DOCKERFILE = "Dockerfile_tor_da"
DIRECTORY_AUTHORITY_IP = "100.20.15.18"


class Tor(BaseService):
    def __init__(self, docker_network, templates):
        super().__init__(docker_network)
        self.templates = templates
        self.service = {
            "build": {
                "context": str(self.templates),
                "dockerfile": DOCKERFILE,
            },
            "container_name": f"{self.docker_network}_tor",
            "networks": {
                self.docker_network: {
                    "ipv4_address": DIRECTORY_AUTHORITY_IP,
                }
            },
        }
