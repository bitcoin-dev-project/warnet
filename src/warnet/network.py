import json
import shutil
from pathlib import Path

from rich import print

from .bitcoin import _rpc
from .constants import (
    LOGGING_HELM_COMMANDS,
    NETWORK_DIR,
    SCENARIOS_DIR,
)
from .k8s import get_mission
from .process import stream_command


def setup_logging_helm() -> bool:
    for command in LOGGING_HELM_COMMANDS:
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
    copy_defaults(
        directory,
        NETWORK_DIR.name,
        NETWORK_DIR,
        ["node-defaults.yaml", "__pycache__", "__init__.py"],
    )


def copy_scenario_defaults(directory: Path):
    """Create the project structure for a warnet project's scenarios"""
    copy_defaults(
        directory,
        SCENARIOS_DIR.name,
        SCENARIOS_DIR,
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
