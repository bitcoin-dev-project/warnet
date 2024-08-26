import json
import os
import random
import subprocess
import sys
from importlib.resources import files
from pathlib import Path

import click
import inquirer
import yaml
from inquirer.themes import GreenPassion

from warnet.k8s import get_default_namespace
from warnet.process import run_command, stream_command

from .admin import admin
from .bitcoin import bitcoin
from .control import down, run, stop
from .deploy import deploy as deploy_command
from .graph import graph
from .image import image
from .network import copy_network_defaults, copy_scenario_defaults
from .status import status as status_command
from .util import DEFAULT_TAG, SUPPORTED_TAGS

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
            click.secho(
                f"Quick start script failed with return code {return_code}", fg="red", bold=True
            )
            click.secho("Install missing requirements before proceeding", fg="yellow")
            return False

        create_project = click.confirm(
            click.style("\nDo you want to create a new project?", fg="blue", bold=True),
            default=True,
        )
        if not create_project:
            click.secho("\nSetup completed successfully!", fg="green", bold=True)
            return True

        default_path = os.path.abspath(os.getcwd())
        project_path = click.prompt(
            click.style("\nEnter the project directory path", fg="blue", bold=True),
            default=default_path,
            type=click.Path(file_okay=False, dir_okay=True, resolve_path=True),
        )

        custom_network = click.confirm(
            click.style("\nDo you want to create a custom network?", fg="blue", bold=True),
            default=True,
        )
        if not custom_network:
            create_warnet_project(Path(project_path))
            click.secho("\nSetup completed successfully!", fg="green", bold=True)
            return True

        network_name = click.prompt(
            click.style("\nEnter the network name", fg="blue", bold=True),
            type=str,
        )

        nodes = click.prompt(
            click.style("\nHow many nodes would you like?", fg="blue", bold=True),
            type=int,
            default=15,
        )
        connections = click.prompt(
            click.style(
                "\nHow many connections would you like each node to have?", fg="blue", bold=True
            ),
            type=int,
            default=8,
        )
        version = click.prompt(
            click.style(
                "\nWhich version would you like nodes to be by default?", fg="blue", bold=True
            ),
            type=click.Choice(SUPPORTED_TAGS, case_sensitive=False),
            default=DEFAULT_TAG,
        )

        click.secho("\nCreating project structure...", fg="yellow", bold=True)
        create_warnet_project(Path(project_path))
        click.secho("\nGenerating custom network...", fg="yellow", bold=True)
        custom_network_path = Path(project_path) / "networks" / network_name
        custom_graph(nodes, connections, version, custom_network_path)
        click.secho("\nSetup completed successfully!", fg="green", bold=True)
        click.echo("\nRun the following command to deploy this network:")
        click.echo(f"warnet deploy {custom_network_path}")
    except Exception as e:
        click.secho(f"An error occurred while running the quick start script:\n\n{e}\n\n", fg="red")
        click.secho(
            "Please report this to https://github.com/bitcoin-dev-project/warnet/issues",
            fg="yellow",
        )
        return False


def create_warnet_project(directory: Path, check_empty: bool = False):
    """Common function to create a warnet project"""
    if check_empty and any(directory.iterdir()):
        click.secho("Warning: Directory is not empty", fg="yellow")
        if not click.confirm("Do you want to continue?", default=True):
            return

    try:
        copy_network_defaults(directory)
        copy_scenario_defaults(directory)
        click.echo(f"Copied network example files to {directory}/networks")
        click.echo(f"Created warnet project structure in {directory}")
    except Exception as e:
        click.secho(f"Error creating project: {e}", fg="red")
        raise e


@cli.command()
@click.argument(
    "directory", type=click.Path(file_okay=False, dir_okay=True, resolve_path=True, path_type=Path)
)
def create(directory: Path):
    """Create a new warnet project in the specified directory"""
    if directory.exists():
        click.secho(f"Error: Directory {directory} already exists", fg="red")
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
            user = content["users"][0]
            user_name = user["name"]
            user_token = user["user"]["token"]
            current_context = content["current-context"]
        flatten_cmd = "kubectl config view --flatten"
        result_flatten = subprocess.run(
            flatten_cmd, shell=True, check=True, capture_output=True, text=True
        )
    except subprocess.CalledProcessError as e:
        click.secho("Error occurred while executing kubectl config view --flatten:", fg="red")
        click.secho(e.stderr, fg="red")
        sys.exit(1)

    if result_flatten.returncode == 0:
        with open(current_kubeconfig, "w") as file:
            file.write(result_flatten.stdout)
            click.secho(f"Authorization file written to: {current_kubeconfig}", fg="green")
    else:
        click.secho("Could not create authorization file", fg="red")
        click.secho(result_flatten.stderr, fg="red")
        sys.exit(result_flatten.returncode)

    try:
        update_cmd = f"kubectl config set-credentials {user_name} --token {user_token}"
        result_update = subprocess.run(
            update_cmd, shell=True, check=True, capture_output=True, text=True
        )
        if result_update.returncode != 0:
            click.secho("Could not update authorization file", fg="red")
            click.secho(result_flatten.stderr, fg="red")
            sys.exit(result_flatten.returncode)
    except subprocess.CalledProcessError as e:
        click.secho("Error occurred while executing kubectl config view --flatten:", fg="red")
        click.secho(e.stderr, fg="red")
        sys.exit(1)

    with open(current_kubeconfig) as file:
        contents = yaml.safe_load(file)

    with open(current_kubeconfig, "w") as file:
        contents["current-context"] = current_context
        yaml.safe_dump(contents, file)

    with open(current_kubeconfig) as file:
        contents = yaml.safe_load(file)
        click.secho(
            f"\nwarnet's current context is now set to: {contents['current-context']}", fg="green"
        )


@cli.command()
@click.argument("pod_name", type=str, default="")
@click.option("--follow", "-f", is_flag=True, default=False, help="Follow logs")
def logs(pod_name: str, follow: bool):
    """Show the logs of a pod"""
    follow_flag = "--follow" if follow else ""
    namespace = get_default_namespace()

    if pod_name:
        try:
            command = f"kubectl logs pod/{pod_name} -n {namespace} {follow_flag}"
            stream_command(command)
            return
        except Exception as e:
            print(f"Could not find the pod {pod_name}: {e}")

    try:
        pods = run_command(f"kubectl get pods -n {namespace} -o json")
        pods = json.loads(pods)
        pod_list = [item["metadata"]["name"] for item in pods["items"]]
    except Exception as e:
        print(f"Could not fetch any pods in namespace {namespace}: {e}")
        return

    if not pod_list:
        print(f"Could not fetch any pods in namespace {namespace}")
        return

    q = [
        inquirer.List(
            name="pod",
            message="Please choose a pod",
            choices=pod_list,
        )
    ]
    selected = inquirer.prompt(q, theme=GreenPassion())
    if selected:
        pod_name = selected["pod"]
        try:
            command = f"kubectl logs pod/{pod_name} -n {namespace} {follow_flag}"
            stream_command(command)
        except Exception as e:
            print(f"Please consider waiting for the pod to become available. Encountered: {e}")
    else:
        pass  # cancelled by user


if __name__ == "__main__":
    cli()


def custom_graph(num_nodes: int, num_connections: int, version: str, datadir: Path):
    datadir.mkdir(parents=False, exist_ok=False)
    # Generate network.yaml
    nodes = []

    for i in range(num_nodes):
        node = {"name": f"tank-{i:04d}", "connect": [], "image": {"tag": version}}

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

    network_yaml_data = {"nodes": nodes}

    with open(os.path.join(datadir, "network.yaml"), "w") as f:
        yaml.dump(network_yaml_data, f, default_flow_style=False)

    # Generate defaults.yaml
    default_yaml_path = files("resources.networks").joinpath("6_node_bitcoin/node-defaults.yaml")
    with open(str(default_yaml_path)) as f:
        defaults_yaml_content = f.read()

    with open(os.path.join(datadir, "node-defaults.yaml"), "w") as f:
        f.write(defaults_yaml_content)

    click.echo(
        f"Project '{datadir}' has been created with 'network.yaml' and 'node-defaults.yaml'."
    )
