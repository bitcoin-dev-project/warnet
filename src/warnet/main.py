import json
import os
import platform
import random
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Callable

import click
import inquirer
import yaml
from inquirer.themes import GreenPassion

from warnet.constants import (
    DEFAULT_TAG,
    DEFAULTS_FILE,
    NETWORK_DIR,
    NETWORK_FILE,
    SRC_DIR,
    SUPPORTED_TAGS,
)
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

QUICK_START_PATH = SRC_DIR.joinpath("resources", "scripts", "quick_start.sh")


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
    print("                 │  Welcome to the Warnet Quickstart │")
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
            click.secho("Please re-run Quickstart.", fg="yellow")
            sys.exit(1)

        if ToolStatus.Unsatisfied in check_results:
            click.secho(
                "Please fix the installation issues above and try quickstart again.", fg="yellow"
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


@cli.command()
@click.argument(
    "directory", type=click.Path(file_okay=False, dir_okay=True, resolve_path=True, path_type=Path)
)
def create(directory: Path):
    """Create a new warnet project in the specified directory"""
    if directory.exists():
        click.secho(f"Error: Directory {directory} already exists", fg="red")
        return

    answers = {}

    # Network name
    network_name = inquirer.prompt(
        [
            inquirer.Text(
                "network_name",
                message=click.style("Choose a network name", fg="blue", bold=True),
                validate=lambda _, x: len(x) > 0,
            )
        ]
    )
    if network_name is None:
        click.secho("Setup cancelled by user.", fg="yellow")
        return False
    answers.update(network_name)

    # Number of nodes
    nodes_question = inquirer.prompt(
        [
            inquirer.List(
                "nodes",
                message=click.style(
                    "How many nodes would you like in the network?", fg="blue", bold=True
                ),
                choices=["8", "12", "20", "50", "other"],
                default="12",
            )
        ]
    )
    if nodes_question is None:
        click.secho("Setup cancelled by user.", fg="yellow")
        return False

    if nodes_question["nodes"] == "other":
        custom_nodes = inquirer.prompt(
            [
                inquirer.Text(
                    "nodes",
                    message=click.style("Enter the number of nodes", fg="blue", bold=True),
                    validate=lambda _, x: int(x) > 0,
                )
            ]
        )
        if custom_nodes is None:
            click.secho("Setup cancelled by user.", fg="yellow")
            return False
        answers["nodes"] = custom_nodes["nodes"]
    else:
        answers["nodes"] = nodes_question["nodes"]

    # Number of connections
    connections_question = inquirer.prompt(
        [
            inquirer.List(
                "connections",
                message=click.style(
                    "How many connections would you like each node to have?",
                    fg="blue",
                    bold=True,
                ),
                choices=["0", "1", "2", "8", "12", "other"],
                default="8",
            )
        ]
    )
    if connections_question is None:
        click.secho("Setup cancelled by user.", fg="yellow")
        return False

    if connections_question["connections"] == "other":
        custom_connections = inquirer.prompt(
            [
                inquirer.Text(
                    "connections",
                    message=click.style("Enter the number of connections", fg="blue", bold=True),
                    validate=lambda _, x: int(x) >= 0,
                )
            ]
        )
        if custom_connections is None:
            click.secho("Setup cancelled by user.", fg="yellow")
            return False
        answers["connections"] = custom_connections["connections"]
    else:
        answers["connections"] = connections_question["connections"]

    # Version
    version_question = inquirer.prompt(
        [
            inquirer.List(
                "version",
                message=click.style(
                    "Which version would you like nodes to run by default?", fg="blue", bold=True
                ),
                choices=SUPPORTED_TAGS,
                default=DEFAULT_TAG,
            )
        ]
    )
    if version_question is None:
        click.secho("Setup cancelled by user.", fg="yellow")
        return False
    answers.update(version_question)
    fork_observer = click.prompt(
        click.style(
            "\nWould you like to enable fork-observer on the network?", fg="blue", bold=True
        ),
        type=bool,
        default=True,
    )
    fork_observer_query_interval = 20
    if fork_observer:
        fork_observer_query_interval = click.prompt(
            click.style(
                "\nHow often would you like fork-observer to query node status (seconds)?",
                fg="blue",
                bold=True,
            ),
            type=int,
            default=20,
        )

    click.secho("\nCreating project structure...", fg="yellow", bold=True)
    project_path = Path(os.path.expanduser(directory))
    create_warnet_project(project_path)

    click.secho("\nGenerating custom network...", fg="yellow", bold=True)
    custom_network_path = project_path / "networks" / answers["network_name"]
    custom_graph(
        int(answers["nodes"]),
        int(answers["connections"]),
        answers["version"],
        custom_network_path,
        fork_observer,
        fork_observer_query_interval,
    )
    click.secho("\nSetup completed successfully!", fg="green", bold=True)

    click.echo(
        f"\nEdit the network files found in {custom_network_path} before deployment if you want to customise the network."
    )
    if fork_observer:
        click.echo(
            "If you enabled fork-observer you must forward the port from the cluster to your local machine:\n"
            "`kubectl port-forward fork-observer 2323`\n"
            "fork-observer will then be available at web address: localhost:2323"
        )

    click.echo("\nWhen you're ready, run the following command to deploy this network:")
    click.echo(f"warnet deploy {custom_network_path}")


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

    with open(os.path.join(datadir, NETWORK_FILE), "w") as f:
        yaml.dump(network_yaml_data, f, default_flow_style=False)

    # Generate node-defaults.yaml
    default_yaml_path = NETWORK_DIR.joinpath(DEFAULTS_FILE)
    with open(str(default_yaml_path)) as f:
        defaults_yaml_content = f.read()

    with open(os.path.join(datadir, DEFAULTS_FILE), "w") as f:
        f.write(defaults_yaml_content)

    click.echo(f"Project '{datadir}' has been created with '{NETWORK_FILE}' and '{DEFAULTS_FILE}'.")


if __name__ == "__main__":
    cli()
