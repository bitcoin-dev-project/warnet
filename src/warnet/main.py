import os
import subprocess
from importlib.resources import files
from pathlib import Path

import click
from rich import print as richprint

from .admin import admin
from .bitcoin import bitcoin
from .graph import graph
from .image import image
from .network import copy_network_defaults, network
from .scenarios import scenarios

QUICK_START_PATH = files("resources.scripts").joinpath("quick_start.sh")


@click.group()
def cli():
    pass


cli.add_command(bitcoin)
cli.add_command(graph)
cli.add_command(image)
cli.add_command(network)
cli.add_command(scenarios)
cli.add_command(admin)


@cli.command()
def setup():
    """Check Warnet requirements are installed"""
    try:
        process = subprocess.Popen(
            ["/bin/bash", str(QUICK_START_PATH)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            # This preserves colours from grant's lovely script!
            env=dict(os.environ, TERM="xterm-256color"),
        )

        for line in iter(process.stdout.readline, ""):
            print(line, end="", flush=True)

        process.stdout.close()
        return_code = process.wait()

        if return_code != 0:
            print(f"Quick start script failed with return code {return_code}")
            return False
        return True

    except Exception as e:
        print(f"An error occurred while running the quick start script: {e}")
        return False


@cli.command()
@click.argument("directory", type=Path)
def create(directory: Path):
    """Create a new warnet project in the specified directory"""
    full_path = Path()
    full_path = directory if directory.is_absolute() else directory.resolve()
    if os.path.exists(directory):
        richprint(f"[red]Error: Directory {full_path} already exists[/red]")
        return

    copy_network_defaults(full_path)
    richprint(f"[green]Copied network example files to {full_path / 'networks'}[/green]")
    richprint(f"[green]Created warnet project structure in {full_path}[/green]")


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


if __name__ == "__main__":
    cli()
