import os
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

        if create_project:
            default_path = os.path.abspath(os.getcwd())
            project_path = click.prompt(
                "Enter the project directory path",
                default=default_path,
                type=click.Path(file_okay=False, dir_okay=True, resolve_path=True),
            )

            _create(project_path)

        click.echo("Setup completed successfully!")
        return True

    except Exception as e:
        print(f"An error occurred while running the quick start script:\n\n{e}\n\n")
        print("Please report this to https://github.com/bitcoin-dev-project/warnet/issues")
        return False


@cli.command()
@click.argument("directory", type=click.Path(file_okay=False, dir_okay=True, resolve_path=True))
def create(directory: Path):
    """Create a new warnet project in the specified directory"""
    _create(directory)


def _create(directory: Path):
    full_path = Path(directory)
    if full_path.exists():
        richprint(f"[red]Error: Directory {full_path} already exists[/red]")
        return

    try:
        copy_network_defaults(full_path)
        copy_scenario_defaults(full_path)
        richprint(f"[green]Copied network example files to {full_path / 'networks'}[/green]")
        richprint(f"[green]Created warnet project structure in {full_path}[/green]")
    except Exception as e:
        richprint(f"[red]Error creating project: {e}[/red]")


@cli.command()
def init():
    """Initialize a warnet project in the current directory"""
    current_dir = os.getcwd()
    if os.listdir(current_dir):
        richprint("[yellow]Warning: Current directory is not empty[/yellow]")
        if not click.confirm("Do you want to continue?", default=True):
            return

    copy_network_defaults(current_dir)
    richprint(f"[green]Copied network example files to {Path(current_dir) / 'networks'}[/green]")
    richprint(f"[green]Created warnet project structure in {current_dir}[/green]")


@cli.command()
@click.argument("kube_config", type=str)
def auth(kube_config: str) -> None:
    """
    Authorize access to a warnet cluster using a kube config file
    """
    try:
        current_kubeconfig = os.environ.get("KUBECONFIG", os.path.expanduser("~/.kube/config"))
        combined_kubeconfig = (
            f"{current_kubeconfig}:{kube_config}" if current_kubeconfig else kube_config
        )
        os.environ["KUBECONFIG"] = combined_kubeconfig
        command = "kubectl config view --flatten"
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print("Error occurred while executing kubectl config view --flatten:")
        print(e.stderr)
        sys.exit(1)

    if result.returncode == 0:
        with open(current_kubeconfig, "w") as file:
            file.write(result.stdout)
            print(f"Authorization file written to: {current_kubeconfig}")
    else:
        print("Could not create authorization file")
        print(result.stderr)
        sys.exit(result.returncode)

    with open(current_kubeconfig) as file:
        contents = yaml.safe_load(file)
        print("\nUse the following command to switch to a new user:")
        print("   kubectl config use-context [user]\n")
        print("Available users:")
        for context in contents["contexts"]:
            print(f"   {context['name']}")


if __name__ == "__main__":
    cli()
