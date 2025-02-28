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
    # Try to get dynamic version from the Git repository
    # This allows a developer to get up-to-date version information
    # depending on the state of their local git repository
    # (e.g. when installed from source in editable mode).
    try:
        # Check if we're in a git repository
        subprocess.check_output(
            ["git", "rev-parse", "--is-inside-work-tree"], stderr=subprocess.DEVNULL
        )

        # Get the base version from the latest tag
        try:
            tag = (
                subprocess.check_output(
                    ["git", "describe", "--tags", "--abbrev=0"],
                    stderr=subprocess.DEVNULL,
                    text=True,
                )
                .strip()
                .lstrip("v")
            )
        except subprocess.SubprocessError:
            # No tags found
            tag = "0.0.0"

        # Get the short commit hash
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short=8", "HEAD"], stderr=subprocess.DEVNULL, text=True
        ).strip()

        # Check if there are uncommitted changes
        status = subprocess.check_output(
            ["git", "status", "--porcelain"], stderr=subprocess.DEVNULL, text=True
        ).strip()

        # Format the version string to match setup.py
        version_str = tag
        if commit:
            version_str += f".{commit}"
            if status:
                version_str += "-dirty"

        click.echo(f"warnet version {version_str} (from git)")
        return
    except (subprocess.SubprocessError, FileNotFoundError):
        # Git commands failed or git not available, fall back to installed version
        pass

    # Fall back to the version file generated during installation
    try:
        from warnet._version import __version__

        version = __version__
        click.echo(f"warnet version {version}")
    except ImportError:
        click.echo("warnet version unknown")


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
