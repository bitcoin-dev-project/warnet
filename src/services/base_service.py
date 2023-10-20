from pathlib import Path


class BaseService:
    def __init__(self, network_name, config_dir=Path()):
        self.network_name = network_name
        self.config_dir = config_dir
        self.service = {}

    def get_service(self):
        return self.service
