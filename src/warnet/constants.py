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
BTCD_CONTAINER = "btcd"
COMMANDER_CONTAINER = "commander"

# Supported node implementations
IMPLEMENTATION_BITCOINCORE = "bitcoincore"
IMPLEMENTATION_BTCD = "btcd"
SUPPORTED_IMPLEMENTATIONS = [IMPLEMENTATION_BITCOINCORE, IMPLEMENTATION_BTCD]
DEFAULT_IMPLEMENTATION = IMPLEMENTATION_BITCOINCORE


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
DEFAULT_BTCD_IMAGE_REPO = "lucasdbr05/btcd"

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
BTCD_CHART_LOCATION = str(CHARTS_DIR.joinpath("btcd"))
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
HELM_BLESSED_VERSION = "v4.2.2"
HELM_BLESSED_NAME_AND_CHECKSUMS = [
    {
        "name": "helm-v4.2.2-darwin-amd64.tar.gz",
        "checksum": "10c1e36ee8c5f2e2ee25a16599cb03ab74c0953cd889cacb980a49ba4b6574ba",
    },
    {
        "name": "helm-v4.2.2-darwin-arm64.tar.gz",
        "checksum": "5410a0dae3d5d91f45653b161260d9301aabc4ae80ae50a6605d66884b6df8ea",
    },
    {
        "name": "helm-v4.2.2-linux-amd64.tar.gz",
        "checksum": "9adafecab4d406853bba163a70e9f104f47dbbf65ce24b7653bae7e36150bcb6",
    },
    {
        "name": "helm-v4.2.2-linux-arm.tar.gz",
        "checksum": "7e9490169874695e04ab1af47c5620621fc13c84219a258fcc1afdcd40ca7438",
    },
    {
        "name": "helm-v4.2.2-linux-arm64.tar.gz",
        "checksum": "78803142087a0069fa4b50d3f32a84d3ef25c14d1ee8a40fbccf86a6216d2f36",
    },
    {
        "name": "helm-v4.2.2-linux-386.tar.gz",
        "checksum": "8e1fdcda4a476ffc5d1179c7f16d33a3d54267efa08fd720f7678277d68bc2d5",
    },
    {
        "name": "helm-v4.2.2-linux-loong64.tar.gz",
        "checksum": "b8bfe96b8b0b0e2af51af4a00ef521cc5a7e03793aea3568cf8500a63ae05041",
    },
    {
        "name": "helm-v4.2.2-linux-ppc64le.tar.gz",
        "checksum": "814a80fd98eb9e4c5a9d610f3b9c15ffe120c2f5e39df16a2f491723ebc90126",
    },
    {
        "name": "helm-v4.2.2-linux-s390x.tar.gz",
        "checksum": "d84cdf1123f20cfbef19a2af1cd6afe8b00626bd9846bccb9dae978c810c8274",
    },
    {
        "name": "helm-v4.2.2-linux-riscv64.tar.gz",
        "checksum": "f07c105180dff2619ab45134b9b47b7845387e8f3299e12ebe0efb87c7548717",
    },
    {
        "name": "helm-v4.2.2-windows-amd64.zip",
        "checksum": "5fad8562e98c34fa5af3ef904086a5874a6701050f9bf36e30238c975df94dcd",
    },
    {
        "name": "helm-v4.2.2-windows-arm64.zip",
        "checksum": "2e993d6a1dd8197a33e65d8e90b26df9d248ff3501701dea401856aa265a2dab",
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
