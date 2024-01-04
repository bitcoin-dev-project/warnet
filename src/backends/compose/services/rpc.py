from .base_service import BaseService

DOCKERFILE = "Dockerfile_rpc"


class Rpc(BaseService):
    PORT = 9276

    def __init__(self, docker_network, templates):
        super().__init__(docker_network)
        self.templates = templates
        self.service = {
            "build": {
                "context": str(self.templates),
                "dockerfile": DOCKERFILE,
            },
            "container_name": f"{self.docker_network}-rpc",
            "image": f"{self.docker_network}-rpc",
            "ports": [f"{self.PORT}:{self.PORT}"],
        }
