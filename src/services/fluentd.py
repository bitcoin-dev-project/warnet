from .base_service import BaseService

FLUENT_IP = "100.102.108.117"
FLUENT_CONF = "fluent.conf"

class Fluentd(BaseService):
    PORT = 24224

    def __init__(self, docker_network, config_dir):
        super().__init__(docker_network, config_dir)
        self.service = {
            "image": "fluent/fluentd:v1.16-debian-1", # Debian version is recommended officially since it has jemalloc support.
            "container_name": f"{self.docker_network}_fluentd",
            "ports": [f"{self.PORT}:{self.PORT}"],
            "volumes": [
                f"{self.config_dir / FLUENT_CONF}:/fluentd/etc/{FLUENT_CONF}"
            ],
            "command": ["/bin/sh", "-c", f"sleep 10 && fluentd -c /fluentd/etc/{FLUENT_CONF}"],
            "networks": {
                self.docker_network: {
                    "ipv4_address": f"{FLUENT_IP}",
                }
            },
        }
