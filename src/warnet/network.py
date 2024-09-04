import json
import shutil
from importlib.resources import files
from pathlib import Path

from rich import print

from .bitcoin import _rpc
from .k8s import get_mission
from .process import stream_command

WAR_MANIFESTS_FILES = files("resources.manifests")
WAR_NETWORK_FILES = files("resources.networks")
WAR_SCENARIOS_FILES = files("resources.scenarios")

WAR_NETWORK_DIR = WAR_NETWORK_FILES.name
WAR_SCENARIOS_DIR = WAR_SCENARIOS_FILES.name

DEFAULT_NETWORK = Path("6_node_bitcoin")
NETWORK_FILE = "network.yaml"
DEFAULTS_FILE = "node-defaults.yaml"
HELM_COMMAND = "helm upgrade --install --create-namespace"
BITCOIN_CHART_LOCATION = str(files("resources.charts").joinpath("bitcoincore"))


def setup_logging_helm() -> bool:
    helm_commands = [
        "helm repo add grafana https://grafana.github.io/helm-charts",
        "helm repo add prometheus-community https://prometheus-community.github.io/helm-charts",
        "helm repo update",
        f"helm upgrade --install --namespace warnet-logging --create-namespace --values {WAR_MANIFESTS_FILES}/loki_values.yaml loki grafana/loki --version 5.47.2",
        "helm upgrade --install --namespace warnet-logging promtail grafana/promtail",
        "helm upgrade --install --namespace warnet-logging prometheus prometheus-community/kube-prometheus-stack --namespace warnet-logging --set grafana.enabled=false",
        f"helm upgrade --install --namespace warnet-logging loki-grafana grafana/grafana --values {WAR_MANIFESTS_FILES}/grafana_values.yaml",
    ]

    for command in helm_commands:
        if not stream_command(command):
            print(f"Failed to run Helm command: {command}")
            return False
    return True


def copy_defaults(directory: Path, target_subdir: str, source_path: Path, exclude_list: list[str]):
    """Generic function to copy default files and directories"""
    target_dir = directory / target_subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    print(f"Creating directory: {target_dir}")

    def should_copy(item: Path) -> bool:
        return item.name not in exclude_list

    for item in source_path.iterdir():
        if should_copy(item):
            if item.is_file():
                shutil.copy2(item, target_dir)
                print(f"Copied file: {item.name}")
            elif item.is_dir():
                shutil.copytree(item, target_dir / item.name, dirs_exist_ok=True)
                print(f"Copied directory: {item.name}")

    print(f"Finished copying files to {target_dir}")


def copy_network_defaults(directory: Path):
    """Create the project structure for a warnet project's network"""
    copy_defaults(directory, WAR_NETWORK_DIR, WAR_NETWORK_FILES.joinpath(), [])


def copy_scenario_defaults(directory: Path):
    """Create the project structure for a warnet project's scenarios"""
    copy_defaults(
        directory,
        WAR_SCENARIOS_DIR,
        WAR_SCENARIOS_FILES.joinpath(),
        ["__init__.py", "__pycache__", "commander.py"],
    )


def _connected():
    tanks = get_mission("tank")
    for tank in tanks:
        # Get actual
        peerinfo = json.loads(_rpc(tank.metadata.name, "getpeerinfo", ""))
        manuals = 0
        for peer in peerinfo:
            if peer["connection_type"] == "manual":
                manuals += 1
        # Even if more edges are specified, bitcoind only allows
        # 8 manual outbound connections

        print("manual " + str(manuals))
        print(tank.metadata.annotations["init_peers"])
        if min(8, int(tank.metadata.annotations["init_peers"])) > manuals:
            print("Network not connected")
            return False
    print("Network connected")
    return True
