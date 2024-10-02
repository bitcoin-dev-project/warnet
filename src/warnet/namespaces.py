import shutil
from pathlib import Path

import click

from .constants import (
    DEFAULT_NAMESPACES,
    DEFAULTS_NAMESPACE_FILE,
    NAMESPACES_DIR,
    NAMESPACES_FILE,
)
from .k8s import CoreV1Api, V1Status, get_static_client


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


@namespaces.command()
def list():
    """List all namespaces with 'warnet-' prefix"""
    sclient: CoreV1Api = get_static_client()
    all_namespaces = sclient.list_namespace()
    warnet_namespaces = [
        ns.metadata.name for ns in all_namespaces.items if ns.metadata.name.startswith("warnet-")
    ]
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
    sclient: CoreV1Api = get_static_client()
    if destroy_all:
        all_namespaces = sclient.list_namespace()
        warnet_namespaces = [
            ns.metadata.name
            for ns in all_namespaces.items
            if ns.metadata.name.startswith("warnet-")
        ]

        if not warnet_namespaces:
            print("No warnet namespaces found to destroy.")
            return

        for ns in warnet_namespaces:
            resp: V1Status = sclient.delete_namespace(ns)
            if resp.status:
                print(f"Destroyed namespace: {ns} with {resp.status}")
            else:
                print(f"Failed to destroy namespace: {ns}")
    elif namespace:
        if not namespace.startswith("warnet-"):
            print("Error: Can only destroy namespaces with 'warnet-' prefix")
            return

        resp: V1Status = sclient.delete_namespace(namespace)
        if resp.status:
            print(f"Destroying namespace: {namespace} with {resp.status}")
        else:
            print(f"Failed to destroy namespace: {namespace}")
    else:
        print("Error: Please specify a namespace or use --all flag.")
