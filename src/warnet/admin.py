import os
from pathlib import Path

import click
from rich import print as richprint

from .constants import NETWORK_DIR
from .namespaces import copy_namespaces_defaults, namespaces
from .network import copy_network_defaults


@click.group(name="admin", hidden=True)
def admin():
    """Admin commands for warnet project management"""
    pass


admin.add_command(namespaces)


@admin.command()
def init():
    """Initialize a warnet project in the current directory"""
    current_dir = os.getcwd()
    if os.listdir(current_dir):
        richprint("[yellow]Warning: Current directory is not empty[/yellow]")
        if not click.confirm("Do you want to continue?", default=True):
            return

    copy_network_defaults(Path(current_dir))
    copy_namespaces_defaults(Path(current_dir))
    richprint(
        f"[green]Copied network and namespace example files to {Path(current_dir) / NETWORK_DIR.name}[/green]"
    )
    richprint(f"[green]Created warnet project structure in {current_dir}[/green]")
