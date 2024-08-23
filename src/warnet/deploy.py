import tempfile
from pathlib import Path

import click
import yaml

from .k8s import get_default_namespace
from .namespaces import (
    BITCOIN_CHART_LOCATION as NAMESPACES_CHART_LOCATION,
)
from .namespaces import (
    DEFAULTS_FILE as NAMESPACES_DEFAULTS_FILE,
)
from .namespaces import (
    NAMESPACES_FILE,
)
from .network import (
    BITCOIN_CHART_LOCATION as NETWORK_CHART_LOCATION,
)
from .network import (
    DEFAULTS_FILE as NETWORK_DEFAULTS_FILE,
)

# Import necessary functions and variables from network.py and namespaces.py
from .network import (
    NETWORK_FILE,
)
from .process import stream_command

HELM_COMMAND = "helm upgrade --install --create-namespace"


def validate_directory(ctx, param, value):
    directory = Path(value)
    if not directory.is_dir():
        raise click.BadParameter(f"'{value}' is not a valid directory.")
    if not (directory / NETWORK_FILE).exists() and not (directory / NAMESPACES_FILE).exists():
        raise click.BadParameter(
            f"'{value}' does not contain a valid network.yaml or namespaces.yaml file."
        )
    return directory


@click.command()
@click.argument(
    "directory",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    callback=validate_directory,
)
def deploy(directory):
    """Deploy a warnet with topology loaded from <directory>"""
    directory = Path(directory)

    if (directory / NETWORK_FILE).exists():
        deploy_network(directory)
    elif (directory / NAMESPACES_FILE).exists():
        deploy_namespaces(directory)
    else:
        click.echo(
            "Error: Neither network.yaml nor namespaces.yaml found in the specified directory."
        )


def deploy_network(directory: Path):
    network_file_path = directory / NETWORK_FILE
    defaults_file_path = directory / NETWORK_DEFAULTS_FILE

    with network_file_path.open() as f:
        network_file = yaml.safe_load(f)

    namespace = get_default_namespace()

    for node in network_file["nodes"]:
        click.echo(f"Deploying node: {node.get('name')}")
        try:
            temp_override_file_path = ""
            node_name = node.get("name")
            node_config_override = {k: v for k, v in node.items() if k != "name"}

            cmd = f"{HELM_COMMAND} {node_name} {NETWORK_CHART_LOCATION} --namespace {namespace} -f {defaults_file_path}"

            if node_config_override:
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".yaml", delete=False
                ) as temp_file:
                    yaml.dump(node_config_override, temp_file)
                    temp_override_file_path = Path(temp_file.name)
                cmd = f"{cmd} -f {temp_override_file_path}"

            if not stream_command(cmd):
                click.echo(f"Failed to run Helm command: {cmd}")
                return
        except Exception as e:
            click.echo(f"Error: {e}")
            return
        finally:
            if temp_override_file_path:
                Path(temp_override_file_path).unlink()


def deploy_namespaces(directory: Path):
    namespaces_file_path = directory / NAMESPACES_FILE
    defaults_file_path = directory / NAMESPACES_DEFAULTS_FILE

    with namespaces_file_path.open() as f:
        namespaces_file = yaml.safe_load(f)

    names = [n.get("name") for n in namespaces_file["namespaces"]]
    for n in names:
        if not n.startswith("warnet-"):
            click.echo(
                f"Failed to create namespace: {n}. Namespaces must start with a 'warnet-' prefix."
            )
            return

    for namespace in namespaces_file["namespaces"]:
        click.echo(f"Deploying namespace: {namespace.get('name')}")
        try:
            temp_override_file_path = Path()
            namespace_name = namespace.get("name")
            namespace_config_override = {k: v for k, v in namespace.items() if k != "name"}

            cmd = f"{HELM_COMMAND} {namespace_name} {NAMESPACES_CHART_LOCATION} -f {defaults_file_path}"

            if namespace_config_override:
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".yaml", delete=False
                ) as temp_file:
                    yaml.dump(namespace_config_override, temp_file)
                    temp_override_file_path = Path(temp_file.name)
                cmd = f"{cmd} -f {temp_override_file_path}"

            if not stream_command(cmd):
                click.echo(f"Failed to run Helm command: {cmd}")
                return
        except Exception as e:
            click.echo(f"Error: {e}")
            return
        finally:
            if temp_override_file_path.exists():
                temp_override_file_path.unlink()
