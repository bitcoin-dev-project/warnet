from .base_service import BaseService


class ForkObserverABC(BaseService):
    PORT = 12324

    def __init__(self, network_name, fork_observer_config):
        super().__init__(network_name)
        self.fork_observer_config = fork_observer_config
        self.name = "fork-observer"
