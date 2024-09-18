import os
from importlib.resources import files
from pathlib import Path

# Constants used throughout the project
# Storing as constants for now but we might want a more sophisticated config management
# at some point.
SUPPORTED_TAGS = ["27.0", "26.0", "25.1", "24.2", "23.2", "22.2"]
DEFAULT_TAG = SUPPORTED_TAGS[0]
WEIGHTED_TAGS = [
    tag for index, tag in enumerate(reversed(SUPPORTED_TAGS)) for _ in range(index + 1)
]

DEFAULT_NAMESPACE = "warnet"
LOGGING_NAMESPACE = "warnet-logging"
INGRESS_NAMESPACE = "ingress"
HELM_COMMAND = "helm upgrade --install --create-namespace"

# Directories and files for non-python assets, e.g., helm charts, example scenarios, default configs
SRC_DIR = files("warnet")
RESOURCES_DIR = files("resources")
NETWORK_DIR = RESOURCES_DIR.joinpath("networks")
NAMESPACES_DIR = RESOURCES_DIR.joinpath("namespaces")
SCENARIOS_DIR = RESOURCES_DIR.joinpath("scenarios")
CHARTS_DIR = RESOURCES_DIR.joinpath("charts")
MANIFESTS_DIR = RESOURCES_DIR.joinpath("manifests")
NETWORK_FILE = "network.yaml"
DEFAULTS_FILE = "node-defaults.yaml"
NAMESPACES_FILE = "namespaces.yaml"
DEFAULTS_NAMESPACE_FILE = "namespace-defaults.yaml"

# Helm charts
BITCOIN_CHART_LOCATION = str(CHARTS_DIR.joinpath("bitcoincore"))
FORK_OBSERVER_CHART = str(CHARTS_DIR.joinpath("fork-observer"))
COMMANDER_CHART = str(CHARTS_DIR.joinpath("commander"))
NAMESPACES_CHART_LOCATION = CHARTS_DIR.joinpath("namespaces")
FORK_OBSERVER_CHART = str(files("resources.charts").joinpath("fork-observer"))
CADDY_CHART = str(files("resources.charts").joinpath("caddy"))
CADDY_INGRESS_NAME = "caddy-ingress"

DEFAULT_NETWORK = Path("6_node_bitcoin")
DEFAULT_NAMESPACES = Path("two_namespaces_two_users")

# Kubeconfig related stuffs
KUBECONFIG = os.environ.get("KUBECONFIG", os.path.expanduser("~/.kube/config"))

# TODO: all of this logging stuff should be a helm chart
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            "format": "%(asctime)s | %(levelname)-7s | %(name)-8s | %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "detailed": {
            "format": "%(asctime)s | %(levelname)-7s | [%(module)21s:%(lineno)4d] | %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "formatter": "simple",
            "stream": "ext://sys.stdout",
        },
        "stderr": {
            "class": "logging.StreamHandler",
            "level": "WARNING",
            "formatter": "simple",
            "stream": "ext://sys.stderr",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "DEBUG",
            "formatter": "detailed",
            "filename": "warnet.log",
            "maxBytes": 16000000,
            "backupCount": 3,
        },
    },
    "loggers": {
        "root": {"level": "DEBUG", "handlers": ["stdout", "stderr", "file"]},
        "urllib3.connectionpool": {"level": "WARNING", "propagate": 1},
        "kubernetes.client.rest": {"level": "WARNING", "propagate": 1},
        "werkzeug": {"level": "WARNING", "propagate": 1},
    },
}

# Helm commands for logging setup
# TODO: also lots of hardcode stuff in these helm commands, will need to fix this when moving to helm charts
LOGGING_HELM_COMMANDS = [
    "helm repo add grafana https://grafana.github.io/helm-charts",
    "helm repo add prometheus-community https://prometheus-community.github.io/helm-charts",
    "helm repo update",
    f"helm upgrade --install --namespace warnet-logging --create-namespace --values {MANIFESTS_DIR}/loki_values.yaml loki grafana/loki --version 5.47.2",
    "helm upgrade --install --namespace warnet-logging promtail grafana/promtail",
    "helm upgrade --install --namespace warnet-logging prometheus prometheus-community/kube-prometheus-stack --namespace warnet-logging --set grafana.enabled=false",
    f"helm upgrade --install grafana-dashboards {CHARTS_DIR}/grafana-dashboards --namespace warnet-logging",
    f"helm upgrade --install --namespace warnet-logging loki-grafana grafana/grafana --values {MANIFESTS_DIR}/grafana_values.yaml",
]


INGRESS_HELM_COMMANDS = [
    "helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx",
    "helm repo update",
    f"helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx --namespace {INGRESS_NAMESPACE} --create-namespace",
]

# Helm binary
HELM_LATEST_URL = "https://get.helm.sh/helm-latest-version"
HELM_DOWNLOAD_URL_STUB = "https://get.helm.sh/"
HELM_BINARY_NAME = "helm"
