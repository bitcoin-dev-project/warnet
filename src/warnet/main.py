import subprocess

import click

from .admin import admin
from .bitcoin import bitcoin
from .control import down, logs, run, snapshot, stop
from .dashboard import dashboard
from .deploy import deploy
from .graph import create, graph, import_network
from .image import image
from .ln import ln
from .project import init, new, setup
from .status import status
from .users import auth


@click.group()
def cli():
    pass


@click.command()
def version() -> None:
    """Display the installed version of warnet"""
    # First try to get the version from the installed package
    try:
        from warnet._version import __version__
        version_str = __version__
    except ImportError:
        version_str = "0.0.0"
    
    # Try to get git commit to append
    try:
        # Check if we're in a git repository
        subprocess.check_output(
            ["git", "rev-parse", "--is-inside-work-tree"], stderr=subprocess.DEVNULL
        )

        # Get the short commit hash
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short=8", "HEAD"], stderr=subprocess.DEVNULL, text=True
        ).strip()

        # If we have a commit hash, append it to the version
        # Don't append if already has a hash
        if commit and "-" not in version_str:  
            version_str = f"{version_str}-{commit}"

        click.echo(f"warnet version {version_str}")
    except (subprocess.SubprocessError, FileNotFoundError):
        # Git commands failed or git not available, just use the version without the commit
        click.echo(f"warnet version {version_str}")


cli.add_command(admin)
cli.add_command(auth)
cli.add_command(bitcoin)
cli.add_command(deploy)
cli.add_command(down)
cli.add_command(dashboard)
cli.add_command(graph)
cli.add_command(import_network)
cli.add_command(image)
cli.add_command(init)
cli.add_command(logs)
cli.add_command(ln)
cli.add_command(new)
cli.add_command(run)
cli.add_command(setup)
cli.add_command(snapshot)
cli.add_command(status)
cli.add_command(stop)
cli.add_command(create)
cli.add_command(version)

if __name__ == "__main__":
    cli()
