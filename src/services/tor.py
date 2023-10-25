from .base_service import BaseService


class TorABC(BaseService):

    def __init__(self, network_name, templates):
        super().__init__(network_name)
        self.templates = templates
        self.name = "tor"

