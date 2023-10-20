from .base_service import BaseService


class FluentdABC(BaseService):
    FLUENT_CONF = "fluent.conf"
    PORT = 24224

    def __init__(self, network_name, config_dir):
        super().__init__(network_name, config_dir)
        self.name = "fluentd"
