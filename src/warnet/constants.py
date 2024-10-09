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

DEFAULT_NAMESPACE = "default"
LOGGING_NAMESPACE = "warnet-logging"
INGRESS_NAMESPACE = "ingress"
WARGAMES_NAMESPACE_PREFIX = "wargames-"
KUBE_INTERNAL_NAMESPACES = ["kube-node-lease", "kube-public", "kube-system", "kubernetes-dashboard"]
HELM_COMMAND = "helm upgrade --install"

TANK_MISSION = "tank"
COMMANDER_MISSION = "commander"

BITCOINCORE_CONTAINER = "bitcoincore"
COMMANDER_CONTAINER = "commander"

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
    "helm upgrade --install --namespace warnet-logging promtail grafana/promtail --create-namespace",
    "helm upgrade --install --namespace warnet-logging prometheus prometheus-community/kube-prometheus-stack --namespace warnet-logging --create-namespace --set grafana.enabled=false",
    f"helm upgrade --install grafana-dashboards {CHARTS_DIR}/grafana-dashboards --namespace warnet-logging --create-namespace",
    f"helm upgrade --install --namespace warnet-logging --create-namespace loki-grafana grafana/grafana --values {MANIFESTS_DIR}/grafana_values.yaml",
]


INGRESS_HELM_COMMANDS = [
    "helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx",
    "helm repo update",
    f"helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx --namespace {INGRESS_NAMESPACE} --create-namespace",
]

# Helm binary
HELM_DOWNLOAD_URL_STUB = "https://get.helm.sh/"
HELM_BINARY_NAME = "helm"
HELM_BLESSED_VERSION = "v3.16.1"
HELM_BLESSED_NAME_AND_CHECKSUMS = [
    {
        "name": "helm-v3.16.1-darwin-amd64.tar.gz",
        "checksum": "1b194824e36da3e3889920960a93868b541c7888c905a06757e88666cfb562c9",
    },
    {
        "name": "helm-v3.16.1-darwin-arm64.tar.gz",
        "checksum": "405a3b13f0e194180f7b84010dfe86689d7703e80612729882ad71e2a4ef3504",
    },
    {
        "name": "helm-v3.16.1-linux-amd64.tar.gz",
        "checksum": "e57e826410269d72be3113333dbfaac0d8dfdd1b0cc4e9cb08bdf97722731ca9",
    },
    {
        "name": "helm-v3.16.1-linux-arm.tar.gz",
        "checksum": "a15a8ddfc373628b13cd2a987206756004091a1f6a91c3b9ee8de6f0b1e2ce90",
    },
    {
        "name": "helm-v3.16.1-linux-arm64.tar.gz",
        "checksum": "780b5b86f0db5546769b3e9f0204713bbdd2f6696dfdaac122fbe7f2f31541d2",
    },
    {
        "name": "helm-v3.16.1-linux-386.tar.gz",
        "checksum": "92d7a47a90734b50528ffffc99cd1b2d4b9fc0f4291bac92c87ef03406a5a7b2",
    },
    {
        "name": "helm-v3.16.1-linux-ppc64le.tar.gz",
        "checksum": "9f0178957c94516eff9a3897778edb93d78fab1f76751bd282883f584ea81c23",
    },
    {
        "name": "helm-v3.16.1-linux-s390x.tar.gz",
        "checksum": "357f8b441cc535240f1b0ba30a42b44571d4c303dab004c9e013697b97160360",
    },
    {
        "name": "helm-v3.16.1-linux-riscv64.tar.gz",
        "checksum": "9a2cab45b7d9282e9be7b42f86d8034dcaa2e81ab338642884843676c2f6929f",
    },
    {
        "name": "helm-v3.16.1-windows-amd64.zip",
        "checksum": "89952ea1bace0a9498053606296ea03cf743c48294969dfc731e7f78d1dc809a",
    },
    {
        "name": "helm-v3.16.1-windows-arm64.zip",
        "checksum": "fc370a291ed926da5e77acf42006de48e7fd5ff94d20c3f6aa10c04fea66e53c",
    },
]


# Kubectl binary
KUBECTL_BINARY_NAME = "kubectl"
KUBECTL_BLESSED_VERSION = "v1.31.1"
KUBECTL_DOWNLOAD_URL_STUB = f"https://dl.k8s.io/release/{KUBECTL_BLESSED_VERSION}/bin"
KUBECTL_BLESSED_NAME_AND_CHECKSUMS = [
    {
        "system": "linux",
        "arch": "amd64",
        "checksum": "57b514a7facce4ee62c93b8dc21fda8cf62ef3fed22e44ffc9d167eab843b2ae",
    },
    {
        "system": "linux",
        "arch": "arm64",
        "checksum": "3af2451191e27ecd4ac46bb7f945f76b71e934d54604ca3ffc7fe6f5dd123edb",
    },
    {
        "system": "darwin",
        "arch": "amd64",
        "checksum": "4b86d3fb8dee8dd61f341572f1ba13c1030d493f4dc1b4831476f61f3cbb77d0",
    },
    {
        "system": "darwin",
        "arch": "arm64",
        "checksum": "08909b92e62004f4f1222dfd39214085383ea368bdd15c762939469c23484634",
    },
]
