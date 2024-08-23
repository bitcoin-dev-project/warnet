import os
import random
import subprocess
import sys
from importlib.resources import files
from pathlib import Path

import click
import yaml
from rich import print as richprint

from .admin import admin
from .bitcoin import bitcoin
from .control import down, run, stop
from .deploy import deploy as deploy_command
from .graph import graph
from .image import image
from .network import copy_network_defaults, copy_scenario_defaults
from .status import status as status_command
from .util import SUPPORTED_TAGS

QUICK_START_PATH = files("resources.scripts").joinpath("quick_start.sh")


@click.group()
def cli():
    pass


cli.add_command(bitcoin)
cli.add_command(deploy_command)
cli.add_command(graph)
cli.add_command(image)
cli.add_command(status_command)
cli.add_command(admin)
cli.add_command(stop)
cli.add_command(down)
cli.add_command(run)


@cli.command()
def quickstart():
    """Setup warnet"""
    try:
        process = subprocess.Popen(
            ["/bin/bash", str(QUICK_START_PATH)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            env=dict(os.environ, TERM="xterm-256color"),
        )
        for line in iter(process.stdout.readline, ""):
            click.echo(line, nl=False)
        process.stdout.close()
        return_code = process.wait()
        if return_code != 0:
            click.echo(f"Quick start script failed with return code {return_code}")
            click.echo("Install missing requirements before proceeding")
            return False

        create_project = click.confirm("Do you want to create a new project?", default=True)
        if not create_project:
            click.echo("Setup completed successfully!")
            return True

        default_path = os.path.abspath(os.getcwd())
        project_path = click.prompt(
            "Enter the project directory path",
            default=default_path,
            type=click.Path(file_okay=False, dir_okay=True, resolve_path=True),
        )

        custom_network = click.confirm("Do you want to create a custom network?", default=True)
        if not custom_network:
            create_warnet_project(Path(project_path))
            click.echo("Setup completed successfully!")
            return True

        network_name = click.prompt(
            "Enter the network name",
            type=str,
        )
        nodes = click.prompt("How many nodes would you like?", type=int)
        connections = click.prompt("How many connects would you like each node to have?", type=int)
        version = click.prompt(
            "Which version would you like nodes to have by default?",
            type=click.Choice(SUPPORTED_TAGS, case_sensitive=False),
        )

        create_warnet_project(Path(project_path))
        custom_graph(nodes, connections, version, Path(project_path) / "networks" / network_name)

    except Exception as e:
        print(f"An error occurred while running the quick start script:\n\n{e}\n\n")
        print("Please report this to https://github.com/bitcoin-dev-project/warnet/issues")
        return False


def create_warnet_project(directory: Path, check_empty: bool = False):
    """Common function to create a warnet project"""
    if check_empty and any(directory.iterdir()):
        richprint("[yellow]Warning: Directory is not empty[/yellow]")
        if not click.confirm("Do you want to continue?", default=True):
            return

    try:
        copy_network_defaults(directory)
        copy_scenario_defaults(directory)
        richprint(f"[green]Copied network example files to {directory / 'networks'}[/green]")
        richprint(f"[green]Created warnet project structure in {directory}[/green]")
    except Exception as e:
        richprint(f"[red]Error creating project: {e}[/red]")
        raise e


@cli.command()
@click.argument(
    "directory", type=click.Path(file_okay=False, dir_okay=True, resolve_path=True, path_type=Path)
)
def create(directory: Path):
    """Create a new warnet project in the specified directory"""
    if directory.exists():
        richprint(f"[red]Error: Directory {directory} already exists[/red]")
        return
    create_warnet_project(directory)


@cli.command()
def init():
    """Initialize a warnet project in the current directory"""
    current_dir = Path.cwd()
    create_warnet_project(current_dir, check_empty=True)


@cli.command()
@click.argument("kube_config", type=str)
def auth(kube_config: str) -> None:
    """
    Authenticate with a warnet cluster using a kube config file
    """
    try:
        current_kubeconfig = os.environ.get("KUBECONFIG", os.path.expanduser("~/.kube/config"))
        combined_kubeconfig = (
            f"{current_kubeconfig}:{kube_config}" if current_kubeconfig else kube_config
        )
        os.environ["KUBECONFIG"] = combined_kubeconfig
        with open(kube_config) as file:
            content = yaml.safe_load(file)
            for elem in content:
                print(elem)
            content["clusters"][0]
            user = content["users"][0]
            user_name = user["name"]
            user_token = user["user"]["token"]
            content["contexts"][0]
        flatten_cmd = "kubectl config view --flatten"
        result_flatten = subprocess.run(
            flatten_cmd, shell=True, check=True, capture_output=True, text=True
        )
    except subprocess.CalledProcessError as e:
        print("Error occurred while executing kubectl config view --flatten:")
        print(e.stderr)
        sys.exit(1)

    if result_flatten.returncode == 0:
        with open(current_kubeconfig, "w") as file:
            file.write(result_flatten.stdout)
            print(f"Authorization file written to: {current_kubeconfig}")
    else:
        print("Could not create authorization file")
        print(result_flatten.stderr)
        sys.exit(result_flatten.returncode)

    try:
        update_cmd = f"kubectl config set-credentials {user_name} --token {user_token}"
        result_update = subprocess.run(
            update_cmd, shell=True, check=True, capture_output=True, text=True
        )
        if result_update.returncode != 0:
            print("Could not update authorization file")
            print(result_flatten.stderr)
            sys.exit(result_flatten.returncode)
    except subprocess.CalledProcessError as e:
        print("Error occurred while executing kubectl config view --flatten:")
        print(e.stderr)
        sys.exit(1)

    with open(current_kubeconfig) as file:
        contents = yaml.safe_load(file)
        print("\nUse the following command to switch to a new user:")
        print("   kubectl config use-context [user]\n")
        print("Available users:")
        for c in contents["contexts"]:
            print(f"   {c['name']}")


if __name__ == "__main__":
    cli()


def custom_graph(num_nodes: int, num_connections: int, version: str, datadir: Path):
    datadir.mkdir(parents=False, exist_ok=False)
    # Generate network.yaml
    nodes = []

    for i in range(num_nodes):
        node = {"name": f"tank-{i:04d}", "connect": []}

        # Add round-robin connection
        next_node = (i + 1) % num_nodes
        node["connect"].append(f"tank-{next_node:04d}")

        # Add random connections
        available_nodes = list(range(num_nodes))
        available_nodes.remove(i)
        if next_node in available_nodes:
            available_nodes.remove(next_node)

        for _ in range(min(num_connections - 1, len(available_nodes))):
            random_node = random.choice(available_nodes)
            node["connect"].append(f"tank-{random_node:04d}")
            available_nodes.remove(random_node)

        nodes.append(node)

    # Add image tag to the first node
    nodes[0]["image"] = {"tag": "v0.20.0"}

    network_yaml_data = {"nodes": nodes}

    with open(os.path.join(datadir, "network.yaml"), "w") as f:
        yaml.dump(network_yaml_data, f, default_flow_style=False)

    # Generate defaults.yaml
    defaults_yaml_content = """
chain: regtest

collectLogs: true
metricsExport: true

resources: {}
  # We usually recommend not to specify default resources and to leave this as a conscious
  # choice for the user. This also increases chances charts run on environments with little
  # resources, such as Minikube. If you do want to specify resources, uncomment the following
  # lines, adjust them as necessary, and remove the curly braces after 'resources:'.
  # limits:
  #   cpu: 100m
  #   memory: 128Mi
  # requests:
  #   cpu: 100m
  #   memory: 128Mi

image:
  repository: bitcoindevproject/bitcoin
  pullPolicy: IfNotPresent
  # Overrides the image tag whose default is the chart appVersion.
  tag: "27.0"

config: |
  dns=1
"""

    with open(os.path.join(datadir, "defaults.yaml"), "w") as f:
        f.write(defaults_yaml_content.strip())

    click.echo(f"Project '{datadir}' has been created with 'network.yaml' and 'defaults.yaml'.")
