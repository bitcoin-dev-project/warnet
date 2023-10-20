from .base_service import BaseService


DOCKERFILE = "Dockerfile_tor_da"
DIRECTORY_AUTHORITY_IP = "100.20.15.18"


class Tor(BaseService):
    def __init__(self, network_name, templates):
        super().__init__(network_name)
        self.templates = templates
        self.service = {
            "build": {
                "context": str(self.templates),
                "dockerfile": DOCKERFILE,
            },
            "container_name": f"{self.network_name}_tor",
            "networks": {
                self.network_name: {
                    "ipv4_address": DIRECTORY_AUTHORITY_IP,
                }
            },
        }
