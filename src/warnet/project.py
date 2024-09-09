import os
import platform
import random
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum, auto
from importlib.resources import files
from pathlib import Path
from typing import Callable

import click
import inquirer
import yaml

from .graph import inquirer_create_network
from .network import copy_network_defaults, copy_scenario_defaults


@click.command()
def setup():
    """Setup warnet"""

    class ToolStatus(Enum):
        Satisfied = auto()
        Unsatisfied = auto()

    @dataclass
    class ToolInfo:
        tool_name: str
        is_installed_func: Callable[[], tuple[bool, str]]
        install_instruction: str
        install_url: str

        __slots__ = ["tool_name", "is_installed_func", "install_instruction", "install_url"]

    def is_minikube_installed() -> tuple[bool, str]:
        try:
            version_result = subprocess.run(
                ["minikube", "version", "--short"],
                capture_output=True,
                text=True,
            )
            location_result = subprocess.run(
                ["which", "minikube"],
                capture_output=True,
                text=True,
            )
            if version_result.returncode == 0 and location_result.returncode == 0:
                return True, location_result.stdout.strip()
            else:
                return False, ""
        except FileNotFoundError as err:
            return False, str(err)

    def is_minikube_version_valid_on_darwin() -> tuple[bool, str]:
        try:
            version_result = subprocess.run(
                ["minikube", "version", "--short"],
                capture_output=True,
                text=True,
            )
            location_result = subprocess.run(
                ["which", "minikube"],
                capture_output=True,
                text=True,
            )
            if version_result.returncode == 0 and location_result.returncode == 0:
                version = version_result.stdout.strip().split()[-1]  # Get the version number
                return version not in [
                    "v1.32.0",
                    "1.33.0",
                ], f"{location_result.stdout.strip()} ({version})"
            else:
                return False, ""
        except FileNotFoundError as err:
            return False, str(err)

    def is_platform_darwin() -> bool:
        return platform.system() == "Darwin"

    def is_docker_installed() -> tuple[bool, str]:
        try:
            version_result = subprocess.run(["docker", "--version"], capture_output=True, text=True)
            location_result = subprocess.run(
                ["which", "docker"],
                capture_output=True,
                text=True,
            )
            if version_result.returncode == 0 and location_result.returncode == 0:
                return True, location_result.stdout.strip()
            else:
                return False, ""
        except FileNotFoundError as err:
            return False, str(err)

    def is_docker_desktop_running() -> tuple[bool, str]:
        try:
            version_result = subprocess.run(["docker", "info"], capture_output=True, text=True)
            location_result = subprocess.run(
                ["which", "docker"],
                capture_output=True,
                text=True,
            )
            if version_result.returncode == 0 and location_result.returncode == 0:
                return "Docker Desktop" in version_result.stdout, location_result.stdout.strip()
            else:
                return False, ""
        except FileNotFoundError as err:
            return False, str(err)

    def is_kubectl_installed() -> tuple[bool, str]:
        try:
            version_result = subprocess.run(
                ["kubectl", "version", "--client"],
                capture_output=True,
                text=True,
            )
            location_result = subprocess.run(
                ["which", "kubectl"],
                capture_output=True,
                text=True,
            )
            if version_result.returncode == 0 and location_result.returncode == 0:
                return True, location_result.stdout.strip()
            else:
                return False, ""
        except FileNotFoundError as err:
            return False, str(err)

    def is_helm_installed() -> tuple[bool, str]:
        try:
            version_result = subprocess.run(["helm", "version"], capture_output=True, text=True)
            location_result = subprocess.run(
                ["which", "helm"],
                capture_output=True,
                text=True,
            )
            if version_result.returncode == 0 and location_result.returncode == 0:
                return version_result.returncode == 0, location_result.stdout.strip()
            else:
                return False, ""
        except FileNotFoundError as err:
            return False, str(err)

    def check_installation(tool_info: ToolInfo) -> ToolStatus:
        has_good_version, location = tool_info.is_installed_func()
        if not has_good_version:
            instruction_label = click.style("    Instruction: ", fg="yellow", bold=True)
            instruction_text = click.style(f"{tool_info.install_instruction}", fg="yellow")
            url_label = click.style("    URL: ", fg="yellow", bold=True)
            url_text = click.style(f"{tool_info.install_url}", fg="yellow")

            click.secho(f" 💥 {tool_info.tool_name} is not installed. {location}", fg="yellow")
            click.echo(instruction_label + instruction_text)
            click.echo(url_label + url_text)
            return ToolStatus.Unsatisfied
        else:
            click.secho(f" ⭐️ {tool_info.tool_name} is satisfied: {location}", bold=False)
            return ToolStatus.Satisfied

    docker_info = ToolInfo(
        tool_name="Docker",
        is_installed_func=is_docker_installed,
        install_instruction="Install Docker from Docker's official site.",
        install_url="https://docs.docker.com/engine/install/",
    )
    docker_desktop_info = ToolInfo(
        tool_name="Docker Desktop",
        is_installed_func=is_docker_desktop_running,
        install_instruction="Make sure Docker Desktop is installed and running.",
        install_url="https://docs.docker.com/desktop/",
    )
    kubectl_info = ToolInfo(
        tool_name="Kubectl",
        is_installed_func=is_kubectl_installed,
        install_instruction="Install kubectl.",
        install_url="https://kubernetes.io/docs/tasks/tools/install-kubectl/",
    )
    helm_info = ToolInfo(
        tool_name="Helm",
        is_installed_func=is_helm_installed,
        install_instruction="Install Helm from Helm's official site.",
        install_url="https://helm.sh/docs/intro/install/",
    )
    minikube_info = ToolInfo(
        tool_name="Minikube",
        is_installed_func=is_minikube_installed,
        install_instruction="Install Minikube from the official Minikube site.",
        install_url="https://minikube.sigs.k8s.io/docs/start/",
    )
    minikube_version_info = ToolInfo(
        tool_name="Minikube's version",
        is_installed_func=is_minikube_version_valid_on_darwin,
        install_instruction="Install the latest Minikube from the official Minikube site.",
        install_url="https://minikube.sigs.k8s.io/docs/start/",
    )

    print("")
    print("                 ╭───────────────────────────────────╮")
    print("                 │  Welcome to Warnet setup          │")
    print("                 ╰───────────────────────────────────╯")
    print("")
    print("    Let's find out if your system has what it takes to run Warnet...")
    print("")

    try:
        questions = [
            inquirer.List(
                "platform",
                message=click.style("Which platform would you like to use?", fg="blue", bold=True),
                choices=["Minikube", "Docker Desktop"],
            )
        ]
        answers = inquirer.prompt(questions)

        check_results: list[ToolStatus] = []
        if answers:
            if answers["platform"] == "Docker Desktop":
                check_results.append(check_installation(docker_info))
                check_results.append(check_installation(docker_desktop_info))
                check_results.append(check_installation(kubectl_info))
                check_results.append(check_installation(helm_info))
            elif answers["platform"] == "Minikube":
                check_results.append(check_installation(docker_info))
                check_results.append(check_installation(minikube_info))
                if is_platform_darwin():
                    check_results.append(check_installation(minikube_version_info))
                check_results.append(check_installation(kubectl_info))
                check_results.append(check_installation(helm_info))
        else:
            click.secho("Please re-run setup.", fg="yellow")
            sys.exit(1)

        if ToolStatus.Unsatisfied in check_results:
            click.secho(
                "Please fix the installation issues above and try setup again.", fg="yellow"
            )
            sys.exit(1)
        else:
            click.secho(" ⭐️ Warnet prerequisites look good.\n")

    except Exception as e:
        click.echo(f"{e}\n\n")
        click.secho(f"An error occurred while running the quick start script:\n\n{e}\n\n", fg="red")
        click.secho(
            "Please report the above context to https://github.com/bitcoin-dev-project/warnet/issues",
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


@click.command()
@click.argument(
    "directory", type=click.Path(file_okay=False, dir_okay=True, resolve_path=True, path_type=Path)
)
def new(directory: Path):
    """Create a new warnet project in the specified directory"""
    new_internal(directory)


def new_internal(directory: Path, from_init=False):
    if directory.exists() and not from_init:
        click.secho(f"Error: Directory {directory} already exists", fg="red")
        return

    click.secho("\nCreating project structure...", fg="yellow", bold=True)
    project_path = Path(os.path.expanduser(directory))
    create_warnet_project(project_path)

    proj_answers = inquirer.prompt(
        [
            inquirer.Confirm(
                "custom_network",
                message=click.style(
                    "Do you want to create a custom network?", fg="blue", bold=True
                ),
                default=True,
            ),
        ]
    )
    if proj_answers is None:
        click.secho("Setup cancelled by user.", fg="yellow")
        return False
    if proj_answers["custom_network"]:
        click.secho("\nGenerating custom network...", fg="yellow", bold=True)
        custom_network_path = inquirer_create_network(directory)

    click.echo(
        f"\nEdit the network files found in {custom_network_path} before deployment if you want to customise the network."
    )
    click.echo(
        "If you enabled fork-observer you must forward the port from the cluster to your local machine:\n"
        "`kubectl port-forward fork-observer 2323`\n"
        "fork-observer will then be available at web address: localhost:2323"
    )

    click.echo("\nWhen you're ready, run the following command to deploy this network:")
    click.echo(f"  warnet deploy {custom_network_path}")


@click.command()
def init():
    """Initialize a warnet project in the current directory"""
    current_dir = Path.cwd()
    new_internal(directory=current_dir, from_init=True)


def custom_graph(
    num_nodes: int,
    num_connections: int,
    version: str,
    datadir: Path,
    fork_observer: bool,
    fork_obs_query_interval: int,
):
    datadir.mkdir(parents=False, exist_ok=False)
    # Generate network.yaml
    nodes = []
    connections = set()

    for i in range(num_nodes):
        node = {"name": f"tank-{i:04d}", "connect": [], "image": {"tag": version}}

        # Add round-robin connection
        next_node = (i + 1) % num_nodes
        node["connect"].append(f"tank-{next_node:04d}")
        connections.add((i, next_node))

        # Add random connections
        available_nodes = list(range(num_nodes))
        available_nodes.remove(i)
        if next_node in available_nodes:
            available_nodes.remove(next_node)

        for _ in range(min(num_connections - 1, len(available_nodes))):
            random_node = random.choice(available_nodes)
            # Avoid circular loops of A -> B -> A
            if (random_node, i) not in connections:
                node["connect"].append(f"tank-{random_node:04d}")
                connections.add((i, random_node))
                available_nodes.remove(random_node)

        nodes.append(node)

    network_yaml_data = {"nodes": nodes}
    network_yaml_data["fork_observer"] = {
        "enabled": fork_observer,
        "configQueryInterval": fork_obs_query_interval,
    }

    with open(os.path.join(datadir, "network.yaml"), "w") as f:
        yaml.dump(network_yaml_data, f, default_flow_style=False)

    # Generate node-defaults.yaml
    default_yaml_path = files("resources.networks").joinpath("node-defaults.yaml")
    with open(str(default_yaml_path)) as f:
        defaults_yaml_content = f.read()

    with open(os.path.join(datadir, "node-defaults.yaml"), "w") as f:
        f.write(defaults_yaml_content)

    click.echo(
        f"Project '{datadir}' has been created with 'network.yaml' and 'node-defaults.yaml'."
    )
