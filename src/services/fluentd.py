import shutil
from templates import TEMPLATES
from .base_service import BaseService

FLUENT_CONF = "fluent.conf"

class Fluentd(BaseService):
    PORT = 24224

    def __init__(self, docker_network, config_dir):
        super().__init__(docker_network, config_dir)
        self.service = {
            "image": "fluent/fluentd:v1.16-debian-1",  # Debian version is recommended officially since it has jemalloc support.
            "container_name": f"{self.docker_network}-fluentd",
            "ports": [
                f"{self.PORT}:{self.PORT}"
            ],
            "volumes": [
                f"{self.config_dir / FLUENT_CONF}:/fluentd/etc/{FLUENT_CONF}"
            ],
            "command": ["/bin/sh", "-c", f"fluentd -c /fluentd/etc/{FLUENT_CONF}"],
            "healthcheck": {
                "test": ["CMD", "/bin/bash", "-c", f"cat < /dev/null > /dev/tcp/localhost/{self.PORT}"],
                "interval": "5s",           # Check every 5 seconds
                "timeout": "1s",            # Give the check 1 second to complete
                "start_period": "2s",       # Start checking after 2 seconds
                "retries": 3
            }
        }

        shutil.copy(TEMPLATES / FLUENT_CONF, config_dir)
