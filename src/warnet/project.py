import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Callable, Optional

import click
import inquirer
import requests

from .constants import (
    HELM_BINARY_NAME,
    HELM_BLESSED_NAME_AND_CHECKSUMS,
    HELM_BLESSED_VERSION,
    HELM_DOWNLOAD_URL_STUB,
    KUBECTL_BINARY_NAME,
    KUBECTL_BLESSED_NAME_AND_CHECKSUMS,
    KUBECTL_BLESSED_VERSION,
    KUBECTL_DOWNLOAD_URL_STUB,
)
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

    def is_minikube_running() -> tuple[bool, str]:
        try:
            result = subprocess.run(
                ["minikube", "status"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0 and "Running" in result.stdout:
                return True, "minikube is running"
            else:
                return False, ""
        except FileNotFoundError:
            # Minikube command not found
            return False, ""

    def is_docker_running() -> tuple[bool, str]:
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return True, "docker is running"
            else:
                return False, ""
        except FileNotFoundError:
            # Docker command not found
            return False, ""

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

    def is_docker_desktop_kube_running() -> tuple[bool, str]:
        try:
            cluster_info = subprocess.run(
                ["kubectl", "cluster-info", "--request-timeout=1"],
                capture_output=True,
                text=True,
            )
            if cluster_info.returncode == 0:
                indented_output = cluster_info.stdout.strip().replace("\n", "\n\t")
                return True, f"\n\t{indented_output}"
            else:
                return False, ""
        except Exception:
            print()
            return False, "Please enable kubernetes in Docker Desktop"

    def is_kubectl_installed_and_offer_if_not() -> tuple[bool, str]:
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
        except FileNotFoundError:
            print()
            kubectl_answer = inquirer.prompt(
                [
                    inquirer.Confirm(
                        "install_kubectl",
                        message=click.style(
                            "Would you like Warnet to install Kubectl into your virtual environment?",
                            fg="blue",
                            bold=True,
                        ),
                        default=True,
                    ),
                ]
            )
            if kubectl_answer is None:
                msg = "Setup cancelled by user."
                click.secho(msg, fg="yellow")
                return False, msg
            if kubectl_answer["install_kubectl"]:
                click.secho("    Installing Kubectl...", fg="yellow", bold=True)
                install_kubectl_rootlessly_to_venv()
                return is_kubectl_installed_and_offer_if_not()
            return False, "Please install Kubectl."

    def is_helm_installed_and_offer_if_not() -> tuple[bool, str]:
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

        except FileNotFoundError:
            print()
            helm_answer = inquirer.prompt(
                [
                    inquirer.Confirm(
                        "install_helm",
                        message=click.style(
                            "Would you like Warnet to install Helm into your virtual environment?",
                            fg="blue",
                            bold=True,
                        ),
                        default=True,
                    ),
                ]
            )
            if helm_answer is None:
                msg = "Setup cancelled by user."
                click.secho(msg, fg="yellow")
                return False, msg
            if helm_answer["install_helm"]:
                click.secho("    Installing Helm...", fg="yellow", bold=True)
                install_helm_rootlessly_to_venv()
                return is_helm_installed_and_offer_if_not()
            return False, "Please install Helm."

    def check_installation(tool_info: ToolInfo) -> ToolStatus:
        has_good_version, location = tool_info.is_installed_func()
        if not has_good_version:
            instruction_label = click.style("    Instruction: ", fg="yellow", bold=True)
            instruction_text = click.style(f"{tool_info.install_instruction}", fg="yellow")
            url_label = click.style("    URL: ", fg="yellow", bold=True)
            url_text = click.style(f"{tool_info.install_url}", fg="yellow")

            click.secho(f" 💥 {tool_info.tool_name} is not satisfied. {location}", fg="yellow")
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
    docker_running_info = ToolInfo(
        tool_name="Running Docker",
        is_installed_func=is_docker_running,
        install_instruction="Please make sure docker is running",
        install_url="https://docs.docker.com/engine/install/",
    )
    docker_desktop_kube_running = ToolInfo(
        tool_name="Kubernetes Running in Docker Desktop",
        is_installed_func=is_docker_desktop_kube_running,
        install_instruction="Please enable the local kubernetes cluster in Docker Desktop",
        install_url="https://docs.docker.com/desktop/kubernetes/",
    )
    minikube_running_info = ToolInfo(
        tool_name="Running Minikube",
        is_installed_func=is_minikube_running,
        install_instruction="Please make sure minikube is running",
        install_url="https://minikube.sigs.k8s.io/docs/start/",
    )
    kubectl_info = ToolInfo(
        tool_name="Kubectl",
        is_installed_func=is_kubectl_installed_and_offer_if_not,
        install_instruction="Install kubectl.",
        install_url="https://kubernetes.io/docs/tasks/tools/install-kubectl/",
    )
    helm_info = ToolInfo(
        tool_name="Helm",
        is_installed_func=is_helm_installed_and_offer_if_not,
        install_instruction="Install Helm from Helm's official site, or rootlessly install Helm using Warnet's downloader when prompted.",
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

    print("                                                                    ")
    print("                    ╭───────────────────────────╮                   ")
    print("                    │  Welcome to Warnet Setup  │                   ")
    print("                    ╰───────────────────────────╯                   ")
    print("                                                                    ")
    print("    Let's find out if your system has what it takes to run Warnet...")
    print("")

    try:
        questions = [
            inquirer.List(
                "platform",
                message=click.style("Which platform would you like to use?", fg="blue", bold=True),
                choices=[
                    "Minikube",
                    "Docker Desktop",
                    "No Backend (Interacting with remote cluster, see `warnet auth --help`)",
                ],
            )
        ]
        answers = inquirer.prompt(questions)

        check_results: list[ToolStatus] = []
        if answers:
            check_results.append(check_installation(kubectl_info))
            check_results.append(check_installation(helm_info))
            if answers["platform"] == "Docker Desktop":
                check_results.append(check_installation(docker_info))
                check_results.append(check_installation(docker_desktop_info))
                check_results.append(check_installation(docker_running_info))
                check_results.append(check_installation(docker_desktop_kube_running))
            elif answers["platform"] == "Minikube":
                check_results.append(check_installation(docker_info))
                check_results.append(check_installation(docker_running_info))
                check_results.append(check_installation(minikube_info))
                if is_platform_darwin():
                    check_results.append(check_installation(minikube_version_info))
                check_results.append(check_installation(minikube_running_info))
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
        click.secho(f"Warning: Directory {directory} is not empty", fg="yellow")
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
    custom_network_path = ""
    if proj_answers is None:
        click.secho("Setup cancelled by user.", fg="yellow")
        return False
    if proj_answers["custom_network"]:
        click.secho("\nGenerating custom network...", fg="yellow", bold=True)
        custom_network_path = inquirer_create_network(directory)

    if custom_network_path:
        click.echo(
            f"\nEdit the network files found under {custom_network_path}/ before deployment if you want to customise the network."
        )
        click.echo("\nWhen you're ready, run the following command to deploy this network:")
        click.echo(f"  warnet deploy {custom_network_path}")


@click.command()
def init():
    """Initialize a warnet project in the current directory"""
    current_dir = Path.cwd()
    new_internal(directory=current_dir, from_init=True)


def get_os_name_for_helm() -> Optional[str]:
    """Return a short operating system name suitable for downloading a helm binary."""
    uname_sys = platform.system().lower()
    if "linux" in uname_sys:
        return "linux"
    elif uname_sys == "darwin":
        return "darwin"
    elif "win" in uname_sys:
        return "windows"
    return None


def is_in_virtualenv() -> bool:
    """Check if the user is in a virtual environment."""
    return hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    )


def download_file(url, destination):
    click.secho(f"    Downloading {url}", fg="blue")
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(destination, "wb") as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)
    else:
        raise Exception(f"Failed to download {url} (status code {response.status_code})")


def query_arch_from_uname(arch: str) -> Optional[str]:
    if arch.startswith("armv5"):
        return "armv5"
    elif arch.startswith("armv6"):
        return "armv6"
    elif arch.startswith("armv7"):
        return "arm"
    elif arch == "aarch64" or arch == "arm64":
        return "arm64"
    elif arch == "x86":
        return "386"
    elif arch == "x86_64":
        return "amd64"
    elif arch == "i686" or arch == "i386":
        return "386"
    else:
        return None


def write_blessed_kubectl_checksum(system: str, arch: str, dest_path: str):
    checksum = next(
        (
            b["checksum"]
            for b in KUBECTL_BLESSED_NAME_AND_CHECKSUMS
            if b["system"] == system and b["arch"] == arch
        ),
        None,
    )
    if checksum:
        with open(dest_path, "w") as f:
            f.write(checksum)
    else:
        click.secho("Could not find a matching kubectl binary and checksum", fg="red")


def write_blessed_helm_checksum(helm_filename: str, dest_path: str):
    checksum = next(
        (b["checksum"] for b in HELM_BLESSED_NAME_AND_CHECKSUMS if b["name"] == helm_filename), None
    )
    if checksum:
        with open(dest_path, "w") as f:
            f.write(checksum)
    else:
        click.secho("Could not find a matching helm binary and checksum", fg="red")


def verify_checksum(file_path, checksum_path):
    click.secho("    Verifying checksum...", fg="blue")
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)

    with open(checksum_path) as f:
        expected_checksum = f.read().strip()

    if sha256_hash.hexdigest() != expected_checksum:
        raise Exception("Checksum verification failed!")
    click.secho("    Checksum verified.", fg="blue")


def install_to_venv(bin_path, binary_name):
    venv_bin_dir = os.path.join(sys.prefix, "bin")
    dst_path = os.path.join(venv_bin_dir, binary_name)
    shutil.move(bin_path, dst_path)
    os.chmod(dst_path, 0o755)
    click.secho(f"    {binary_name} installed into {dst_path}", fg="blue")


def install_helm_rootlessly_to_venv():
    if not is_in_virtualenv():
        click.secho(
            "Error: You are not in a virtual environment. Please activate a virtual environment and try again.",
            fg="yellow",
        )
        sys.exit(1)

    version = HELM_BLESSED_VERSION

    os_name = get_os_name_for_helm()
    if os_name is None:
        click.secho(
            "Error: Could not determine the operating system of this computer.", fg="yellow"
        )
        sys.exit(1)

    uname_arch = os.uname().machine
    arch = query_arch_from_uname(uname_arch)
    if not arch:
        click.secho(f"No Helm binary candidate for arch: {uname_arch}", fg="red")
        sys.exit(1)

    helm_filename = f"{HELM_BINARY_NAME}-{version}-{os_name}-{arch}.tar.gz"
    helm_url = f"{HELM_DOWNLOAD_URL_STUB}{helm_filename}"

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            helm_archive_path = os.path.join(temp_dir, helm_filename)
            checksum_path = os.path.join(temp_dir, f"{helm_filename}.sha256")

            download_file(helm_url, helm_archive_path)
            write_blessed_helm_checksum(helm_filename, checksum_path)
            verify_checksum(helm_archive_path, checksum_path)

            # Extract Helm and install it in the virtual environment's bin folder
            with tarfile.open(helm_archive_path, "r:gz") as tar:
                tar.extractall(path=temp_dir)
            helm_bin_path = os.path.join(temp_dir, os_name + "-" + arch, HELM_BINARY_NAME)
            install_to_venv(helm_bin_path, HELM_BINARY_NAME)

            click.secho(
                f"    {HELM_BINARY_NAME} {version} installed successfully to your virtual environment!\n",
                fg="blue",
            )

    except Exception as e:
        click.secho(f"Error: {e}\nCould not install helm.", fg="yellow")
        sys.exit(1)


def install_kubectl_rootlessly_to_venv():
    if not is_in_virtualenv():
        click.secho(
            "Error: You are not in a virtual environment. Please activate a virtual environment and try again.",
            fg="yellow",
        )
        sys.exit(1)

    os_name = get_os_name_for_helm()
    if os_name is None:
        click.secho(
            "Error: Could not determine the operating system of this computer.", fg="yellow"
        )
        sys.exit(1)

    uname_arch = os.uname().machine
    arch = query_arch_from_uname(uname_arch)
    if arch not in ["arm64", "amd64"]:
        click.secho(f"No Kubectl binary candidate for arch: {uname_arch}", fg="red")
        sys.exit(1)

    uname_sys = os.uname().sysname.lower()
    if uname_sys not in ["linux", "darwin"]:
        click.secho(f"The following system is not supported: {uname_sys}", fg="red")
        sys.exit(1)

    kubectl_url = f"{KUBECTL_DOWNLOAD_URL_STUB}/{uname_sys}/{arch}/{KUBECTL_BINARY_NAME}"

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            binary_path = os.path.join(temp_dir, KUBECTL_BINARY_NAME)
            checksum_path = os.path.join(temp_dir, f"{KUBECTL_BINARY_NAME}.sha256")

            download_file(kubectl_url, binary_path)
            write_blessed_kubectl_checksum(uname_sys, arch, checksum_path)
            verify_checksum(binary_path, checksum_path)

            install_to_venv(binary_path, KUBECTL_BINARY_NAME)

            click.secho(
                f"    {KUBECTL_BINARY_NAME} {KUBECTL_BLESSED_VERSION} installed successfully to your virtual environment!\n",
                fg="blue",
            )

    except Exception as e:
        click.secho(f"Error: {e}\nCould not install helm.", fg="yellow")
        sys.exit(1)
