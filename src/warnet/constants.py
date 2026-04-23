import os
from enum import Enum
from importlib.resources import files
from pathlib import Path

SUPPORTED_TAGS = []
tags_file_path = Path(__file__).with_name("bitcoincore.tags")
with tags_file_path.open() as f:
    SUPPORTED_TAGS = [line.strip() for line in f if line.strip()][::-1]
DEFAULT_TAG = SUPPORTED_TAGS[0]

DEFAULT_NAMESPACE = "default"
LOGGING_NAMESPACE = "warnet-logging"
INGRESS_NAMESPACE = "ingress"
WARGAMES_NAMESPACE_PREFIX = "wargames-"
KUBE_INTERNAL_NAMESPACES = ["kube-node-lease", "kube-public", "kube-system", "kubernetes-dashboard"]
HELM_COMMAND = "helm upgrade --install"

TANK_MISSION = "tank"
COMMANDER_MISSION = "commander"
LIGHTNING_MISSION = "lightning"

BITCOINCORE_CONTAINER = "bitcoincore"
COMMANDER_CONTAINER = "commander"


class HookValue(Enum):
    PRE_DEPLOY = "preDeploy"
    POST_DEPLOY = "postDeploy"
    PRE_NODE = "preNode"
    POST_NODE = "postNode"
    PRE_NETWORK = "preNetwork"
    POST_NETWORK = "postNetwork"


class WarnetContent(Enum):
    HOOK_VALUE = "hook_value"
    NAMESPACE = "namespace"
    ANNEX = "annex"


class AnnexMember(Enum):
    NODE_NAME = "node_name"


PLUGIN_ANNEX = "annex"

DEFAULT_IMAGE_REPO = "bitcoindevproject/bitcoin"

# Bitcoin Core config
FORK_OBSERVER_RPCAUTH = "forkobserver:1418183465eecbd407010cf60811c6a0$d4e5f0647a63429c218da1302d7f19fe627302aeb0a71a74de55346a25d8057c"
# Fork Observer config
FORK_OBSERVER_RPC_USER = "forkobserver"
FORK_OBSERVER_RPC_PASSWORD = "tabconf2024"

# Directories and files for non-python assets, e.g., helm charts, example scenarios, default configs
SRC_DIR = files("warnet")
RESOURCES_DIR = files("resources")
NETWORK_DIR = RESOURCES_DIR.joinpath("networks")
NAMESPACES_DIR = RESOURCES_DIR.joinpath("namespaces")
SCENARIOS_DIR = RESOURCES_DIR.joinpath("scenarios")
CHARTS_DIR = RESOURCES_DIR.joinpath("charts")
MANIFESTS_DIR = RESOURCES_DIR.joinpath("manifests")
PLUGINS_DIR = RESOURCES_DIR.joinpath("plugins")
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

DEFAULT_NAMESPACES = Path("two_namespaces_two_users")

# Kubeconfig related stuffs
KUBECONFIG = os.environ.get("KUBECONFIG", os.path.expanduser("~/.kube/config"))
KUBECONFIG_UNDO = KUBECONFIG + "_warnet_undo"

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

LOGGING_CRD_COMMANDS = [
    "helm repo add prometheus-community https://prometheus-community.github.io/helm-charts",
    "helm repo update",
    "helm upgrade --install prometheus-operator-crds prometheus-community/prometheus-operator-crds",
]

# Helm commands for logging setup
# TODO: also lots of hardcode stuff in these helm commands, will need to fix this when moving to helm charts
LOGGING_HELM_COMMANDS = [
    "helm repo add grafana https://grafana.github.io/helm-charts",
    "helm repo add prometheus-community https://prometheus-community.github.io/helm-charts",
    "helm repo update",
    f"helm upgrade --install --namespace warnet-logging --create-namespace --values {MANIFESTS_DIR}/loki_values.yaml loki grafana/loki --version 5.47.2",
    "helm upgrade --install --namespace warnet-logging promtail grafana/promtail --create-namespace",
    "helm upgrade --install --namespace warnet-logging prometheus prometheus-community/kube-prometheus-stack --namespace warnet-logging --create-namespace --set grafana.enabled=false --set prometheus.prometheusSpec.maximumStartupDurationSeconds=300",
    f"helm upgrade --install grafana-dashboards {CHARTS_DIR}/grafana-dashboards --namespace warnet-logging --create-namespace",
    f"helm upgrade --install --namespace warnet-logging --create-namespace loki-grafana grafana/grafana --values {MANIFESTS_DIR}/grafana_values.yaml",
]


INGRESS_HELM_COMMANDS = [
    "helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx",
    "helm repo update",
    f"helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx --namespace {INGRESS_NAMESPACE} --create-namespace --set controller.progressDeadlineSeconds=600",
]

# Helm binary
HELM_DOWNLOAD_URL_STUB = "https://get.helm.sh/"
HELM_BINARY_NAME = "helm"
HELM_BLESSED_VERSION = "v4.1.4"
HELM_BLESSED_NAME_AND_CHECKSUMS = [
    {
        "name": "helm-v4.1.4-darwin-amd64.tar.gz",
        "checksum": "abf09c8503ad1d8ef76d3737a058c3456a998aae5f5966fce4bb3031aeb1654e",
    },
    {
        "name": "helm-v4.1.4-darwin-arm64.tar.gz",
        "checksum": "7c2eca678e8001fa863cdf8cbf6ac1b3799f9404a89eb55c08260ef5732e658d",
    },
    {
        "name": "helm-v4.1.4-linux-amd64.tar.gz",
        "checksum": "70b2c30a19da4db264dfd68c8a3664e05093a361cefd89572ffb36f8abfa3d09",
    },
    {
        "name": "helm-v4.1.4-linux-arm.tar.gz",
        "checksum": "c4a7d37032379cc7e82c9c76487d1041b193c9a0fbb4b8f3790230899b830a4f",
    },
    {
        "name": "helm-v4.1.4-linux-arm64.tar.gz",
        "checksum": "13d03672be289045d2ff00e4e345d61de1c6f21c1257a45955a30e8ae036d8f1",
    },
    {
        "name": "helm-v4.1.4-linux-386.tar.gz",
        "checksum": "3e9bcefb85293854367bea931d669bb742974bbd978b3960df921ed129ff40f9",
    },
    {
        "name": "helm-v4.1.4-linux-ppc64le.tar.gz",
        "checksum": "35a48f5db5c655b4471b37be75e76bfb2b23fc8a95d0fa2f0f344f0694336358",
    },
    {
        "name": "helm-v4.1.4-linux-s390x.tar.gz",
        "checksum": "c5653d0b3687f008dc48f80219906b574af3b623ddc114f92383327299ad935e",
    },
    {
        "name": "helm-v4.1.4-linux-riscv64.tar.gz",
        "checksum": "9d747ed5761a6a5c15aa7ad108b65aee917d8e33448690e83a6451b6a48748e6",
    },
    {
        "name": "helm-v4.1.4-windows-amd64.zip",
        "checksum": "bd60f567f667631a2c9b698dfabe5e3cd52eaaf4264163c0a9cae566db8560e8",
    },
    {
        "name": "helm-v4.1.4-windows-arm64.zip",
        "checksum": "d0a651026da4a26b28bdfc3d455ce3dfacbc267182dc2225c2172b1dcc549643",
    },
]


# Kubectl binary
KUBECTL_BINARY_NAME = "kubectl"
KUBECTL_BLESSED_VERSION = "v1.35.1"
KUBECTL_DOWNLOAD_URL_STUB = f"https://dl.k8s.io/release/{KUBECTL_BLESSED_VERSION}/bin"
KUBECTL_BLESSED_NAME_AND_CHECKSUMS = [
    {
        "system": "linux",
        "arch": "amd64",
        "checksum": "36e2f4ac66259232341dd7866952d64a958846470f6a9a6a813b9117bd965207",
    },
    {
        "system": "linux",
        "arch": "arm64",
        "checksum": "706256e21a4e9192ee62d1a007ac0bfcff2b0b26e92cc7baad487a6a5d08ff82",
    },
    {
        "system": "darwin",
        "arch": "amd64",
        "checksum": "07a04d82bc2de2f5d53dfd81f2109ca864f634a82b225257daa2f9c2db15ccef",
    },
    {
        "system": "darwin",
        "arch": "arm64",
        "checksum": "2b000dded317319b1ebca19c2bc70f772c7aaa0e8962fae2d987ba04dd1a1b50",
    },
]
