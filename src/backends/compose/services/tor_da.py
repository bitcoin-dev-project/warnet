from .base_service import BaseService

DOCKERFILE = "Dockerfile_tor_da"
DIRECTORY_AUTHORITY_IP = "100.20.15.18"


class TorDA(BaseService):
    def __init__(self, docker_network):
        super().__init__(docker_network)
        self.service = {
            "container_name": "tor_da",
            "image": "pinheadmz/tor_da:1.0",
            "networks": {
                self.docker_network: {
                    "ipv4_address": DIRECTORY_AUTHORITY_IP,
                }
            },
            "healthcheck": {
                "test": ["CMD-SHELL", "echo -e 'AUTHENTICATE \"\"\r\nGETINFO status/bootstrap-phase\r\nQUIT\r\n' | nc localhost 9051 | grep Done"],
                "interval": "10s",  # Check every 10 seconds
                "timeout": "1s",  # Give the check 1 second to complete
                "start_period": "5s",  # Start checking after 5 seconds
                "retries": 60,  # 60 retries (about 10 minutes)
            },
        }
