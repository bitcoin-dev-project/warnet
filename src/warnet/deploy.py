import subprocess
import sys
import tempfile
from pathlib import Path

import click
import yaml

from .constants import (
    BITCOIN_CHART_LOCATION,
    CADDY_CHART,
    DEFAULTS_FILE,
    DEFAULTS_NAMESPACE_FILE,
    FORK_OBSERVER_CHART,
    HELM_COMMAND,
    INGRESS_HELM_COMMANDS,
    LOGGING_HELM_COMMANDS,
    LOGGING_NAMESPACE,
    NAMESPACES_CHART_LOCATION,
    NAMESPACES_FILE,
    NETWORK_FILE,
)
from .k8s import get_default_namespace, wait_for_ingress_controller, wait_for_pod_ready
from .process import stream_command


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
@click.option("--debug", is_flag=True)
def deploy(directory, debug):
    """Deploy a warnet with topology loaded from <directory>"""
    directory = Path(directory)

    if (directory / NETWORK_FILE).exists():
        dl = deploy_logging_stack(directory, debug)
        deploy_network(directory, debug)
        df = deploy_fork_observer(directory, debug)
        if dl | df:
            deploy_ingress(debug)
            deploy_caddy(directory, debug)
    elif (directory / NAMESPACES_FILE).exists():
        deploy_namespaces(directory)
    else:
        click.echo(
            "Error: Neither network.yaml nor namespaces.yaml found in the specified directory."
        )


def check_logging_required(directory: Path):
    # check if node-defaults has logging or metrics enabled
    default_file_path = directory / DEFAULTS_FILE
    with default_file_path.open() as f:
        default_file = yaml.safe_load(f)
    if default_file.get("collectLogs", False):
        return True
    if default_file.get("metricsExport", False):
        return True

    # check to see if individual nodes have logging enabled
    network_file_path = directory / NETWORK_FILE
    with network_file_path.open() as f:
        network_file = yaml.safe_load(f)
    nodes = network_file.get("nodes", [])
    for node in nodes:
        if node.get("collectLogs", False):
            return True
        if node.get("metricsExport", False):
            return True

    return False


def deploy_logging_stack(directory: Path, debug: bool) -> bool:
    if not check_logging_required(directory):
        return False

    click.echo("Found collectLogs or metricsExport in network definition, Deploying logging stack")

    for command in LOGGING_HELM_COMMANDS:
        if not stream_command(command):
            print(f"Failed to run Helm command: {command}")
            return False
    return True


def deploy_caddy(directory: Path, debug: bool):
    network_file_path = directory / NETWORK_FILE
    with network_file_path.open() as f:
        network_file = yaml.safe_load(f)

    namespace = LOGGING_NAMESPACE
    # TODO: get this from the helm chart
    name = "caddy"

    # Only start if configured in the network file
    if not network_file.get(name, {}).get("enabled", False):
        return

    cmd = f"{HELM_COMMAND} {name} {CADDY_CHART} --namespace {namespace}"
    if debug:
        cmd += " --debug"

    if not stream_command(cmd):
        click.echo(f"Failed to run Helm command: {cmd}")
        return

    wait_for_pod_ready(name, namespace)
    click.echo("\nTo access the warnet dashboard run:\n  warnet dashboard")


def deploy_ingress(debug: bool):
    click.echo("Deploying ingress controller")

    for command in INGRESS_HELM_COMMANDS:
        if not stream_command(command):
            print(f"Failed to run Helm command: {command}")
            return False

    wait_for_ingress_controller()

    return True


def deploy_fork_observer(directory: Path, debug: bool) -> bool:
    network_file_path = directory / NETWORK_FILE
    with network_file_path.open() as f:
        network_file = yaml.safe_load(f)

    # Only start if configured in the network file
    if not network_file.get("fork_observer", {}).get("enabled", False):
        return False

    default_namespace = get_default_namespace()
    namespace = LOGGING_NAMESPACE
    cmd = f"{HELM_COMMAND} 'fork-observer' {FORK_OBSERVER_CHART} --namespace {namespace}"
    if debug:
        cmd += " --debug"

    temp_override_file_path = ""
    override_string = ""

    # Add an entry for each node in the graph
    for i, node in enumerate(network_file["nodes"]):
        node_name = node.get("name")
        node_config = f"""
[[networks.nodes]]
id = {i}
name = "{node_name}"
description = "A node. Just A node."
rpc_host = "{node_name}.{default_namespace}.svc"
rpc_port = 18443
rpc_user = "forkobserver"
rpc_password = "tabconf2024"
"""

        override_string += node_config

    # Create yaml string using multi-line string format
    override_string = override_string.strip()
    v = {"config": override_string}
    v["configQueryinterval"] = network_file.get("fork_observer", {}).get("configQueryinterval", 20)
    yaml_string = yaml.dump(v, default_style="|", default_flow_style=False)

    # Dump to yaml tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as temp_file:
        temp_file.write(yaml_string)
        temp_override_file_path = Path(temp_file.name)

    cmd = f"{cmd} -f {temp_override_file_path}"

    if not stream_command(cmd):
        click.echo(f"Failed to run Helm command: {cmd}")
        return False
    return True


def deploy_network(directory: Path, debug: bool = False):
    network_file_path = directory / NETWORK_FILE
    defaults_file_path = directory / DEFAULTS_FILE

    with network_file_path.open() as f:
        network_file = yaml.safe_load(f)

    namespace = get_default_namespace()

    for node in network_file["nodes"]:
        click.echo(f"Deploying node: {node.get('name')}")
        try:
            temp_override_file_path = ""
            node_name = node.get("name")
            node_config_override = {k: v for k, v in node.items() if k != "name"}

            cmd = f"{HELM_COMMAND} {node_name} {BITCOIN_CHART_LOCATION} --namespace {namespace} -f {defaults_file_path}"
            if debug:
                cmd += " --debug"

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
    defaults_file_path = directory / DEFAULTS_NAMESPACE_FILE

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


def is_windows():
    return sys.platform.startswith("win")


def run_detached_process(command):
    if is_windows():
        # For Windows, use CREATE_NEW_PROCESS_GROUP and DETACHED_PROCESS
        subprocess.Popen(
            command,
            shell=True,
            stdin=None,
            stdout=None,
            stderr=None,
            close_fds=True,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
        )
    else:
        # For Unix-like systems, use nohup and redirect output
        command = f"nohup {command} > /dev/null 2>&1 &"
        subprocess.Popen(command, shell=True, stdin=None, stdout=None, stderr=None, close_fds=True)

    print(f"Started detached process: {command}")
