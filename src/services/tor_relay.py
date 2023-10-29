from .base_service import BaseService

DOCKERFILE = "Dockerfile_tor_relay"


class TorRelay(BaseService):
    def __init__(self, docker_network, templates):
        super().__init__(docker_network)
        self.templates = templates
        self.service = {
            "build": {
                "context": str(self.templates),
                "dockerfile": DOCKERFILE,
            },
            "networks": [ self.docker_network ],
        }
