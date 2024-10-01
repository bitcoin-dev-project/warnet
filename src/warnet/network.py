import json
import shutil
from pathlib import Path

from rich import print

from .bitcoin import _rpc
from .constants import (
    NETWORK_DIR,
    SCENARIOS_DIR,
)
from .k8s import get_mission


def copy_defaults(directory: Path, target_subdir: str, source_path: Path, exclude_list: list[str]):
    """Generic function to copy default files and directories"""
    target_dir = directory / target_subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    print(f"Creating directory: {target_dir}")

    shutil.copytree(
        src=source_path,
        dst=target_dir,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(*exclude_list),
    )

    print(f"Finished copying files to {target_dir}")


def copy_network_defaults(directory: Path):
    """Create the project structure for a warnet project's network"""
    copy_defaults(
        directory,
        NETWORK_DIR.name,
        NETWORK_DIR,
        ["__pycache__", "__init__.py"],
    )


def copy_scenario_defaults(directory: Path):
    """Create the project structure for a warnet project's scenarios"""
    copy_defaults(
        directory,
        SCENARIOS_DIR.name,
        SCENARIOS_DIR,
        ["__pycache__", "test_scenarios"],
    )


def is_connection_manual(peer):
    # newer nodes specify a "connection_type"
    return bool(peer.get("connection_type") == "manual" or peer.get("addnode") is True)


def _connected(end="\n"):
    tanks = get_mission("tank")
    for tank in tanks:
        # Get actual
        try:
            peerinfo = json.loads(
                _rpc(tank.metadata.name, "getpeerinfo", "", namespace=tank.metadata.namespace)
            )
            actual = 0
            for peer in peerinfo:
                if is_connection_manual(peer):
                    actual += 1
            expected = int(tank.metadata.annotations["init_peers"])
            print(
                f"Tank {tank.metadata.name} peers expected: {expected}, actual: {actual}", end=end
            )
            # Even if more edges are specified, bitcoind only allows
            # 8 manual outbound connections
            if min(8, expected) > actual:
                print("\nNetwork not connected")
                return False
        except Exception:
            return False
    print("Network connected                                                           ")
    return True
