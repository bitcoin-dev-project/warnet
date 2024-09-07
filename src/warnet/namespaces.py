import shutil
from pathlib import Path

import click

from .constants import (
    DEFAULT_NAMESPACES,
    DEFAULTS_NAMESPACE_FILE,
    NAMESPACES_DIR,
    NAMESPACES_FILE,
)
from .process import run_command, stream_command


def copy_namespaces_defaults(directory: Path):
    """Create the project structure for a warnet project"""
    (directory / NAMESPACES_DIR.name / DEFAULT_NAMESPACES).mkdir(parents=True, exist_ok=True)
    target_namespaces_defaults = (
        directory / NAMESPACES_DIR.name / DEFAULT_NAMESPACES / DEFAULTS_NAMESPACE_FILE
    )
    target_namespaces_example = (
        directory / NAMESPACES_DIR.name / DEFAULT_NAMESPACES / NAMESPACES_FILE
    )
    shutil.copy2(
        NAMESPACES_DIR / DEFAULT_NAMESPACES / DEFAULTS_NAMESPACE_FILE, target_namespaces_defaults
    )
    shutil.copy2(NAMESPACES_DIR / DEFAULT_NAMESPACES / NAMESPACES_FILE, target_namespaces_example)


@click.group(name="namespaces")
def namespaces():
    """Namespaces commands"""


@click.argument(
    "namespaces_dir", type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path)
)
@namespaces.command()
def list():
    """List all namespaces with 'warnet-' prefix"""
    cmd = "kubectl get namespaces -o jsonpath='{.items[*].metadata.name}'"
    res = run_command(cmd)
    all_namespaces = res.split()
    warnet_namespaces = [ns for ns in all_namespaces if ns.startswith("warnet-")]

    if warnet_namespaces:
        print("Warnet namespaces:")
        for ns in warnet_namespaces:
            print(f"- {ns}")
    else:
        print("No warnet namespaces found.")


@namespaces.command()
@click.option("--all", "destroy_all", is_flag=True, help="Destroy all warnet- prefixed namespaces")
@click.argument("namespace", required=False)
def destroy(destroy_all: bool, namespace: str):
    """Destroy a specific namespace or all warnet- prefixed namespaces"""
    if destroy_all:
        cmd = "kubectl get namespaces -o jsonpath='{.items[*].metadata.name}'"
        res = run_command(cmd)

        # Get the list of namespaces
        all_namespaces = res.split()
        warnet_namespaces = [ns for ns in all_namespaces if ns.startswith("warnet-")]

        if not warnet_namespaces:
            print("No warnet namespaces found to destroy.")
            return

        for ns in warnet_namespaces:
            destroy_cmd = f"kubectl delete namespace {ns}"
            if not stream_command(destroy_cmd):
                print(f"Failed to destroy namespace: {ns}")
            else:
                print(f"Destroyed namespace: {ns}")
    elif namespace:
        if not namespace.startswith("warnet-"):
            print("Error: Can only destroy namespaces with 'warnet-' prefix")
            return

        destroy_cmd = f"kubectl delete namespace {namespace}"
        if not stream_command(destroy_cmd):
            print(f"Failed to destroy namespace: {namespace}")
        else:
            print(f"Destroyed namespace: {namespace}")
    else:
        print("Error: Please specify a namespace or use --all flag.")
