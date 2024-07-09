from enum import Enum

FO_CONF_NAME = "fork_observer_config.toml"
AO_CONF_NAME = "addrman_observer_config.toml"
GRAFANA_PROVISIONING = "grafana-provisioning"
PROM_CONF_NAME = "prometheus.yml"


class ServiceType(Enum):
    BITCOIN = 1
    LIGHTNING = 2
    CIRCUITBREAKER = 3


SERVICES = {
    # "forkobserver": {
    #     "image": "b10c/fork-observer:latest",
    #     "container_name_suffix": "fork-observer",
    #     "warnet_port": "23001",
    #     "container_port": "2323",
    #     "config_files": [f"{FO_CONF_NAME}:/app/config.toml"],
    # },
    # "addrmanobserver": {
    #     "image": "b10c/addrman-observer:latest",
    #     "container_name_suffix": "addrman-observer",
    #     "warnet_port": "23005",
    #     "container_port": "3882",
    #     "config_files": [f"{AO_CONF_NAME}:/app/config.toml"],
    # },
    "simln": {
        "image": "bitcoindevproject/simln:0.2.0",
        "container_name_suffix": "simln",
        "environment": ["LOG_LEVEL=debug", "SIMFILE_PATH=/simln/sim.json"],
        "config_files": ["simln/:/simln"],
    },
}
