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
    try:
        from warnet._version import __version__

        # For PyPI releases, this will be the exact tag (e.g. "1.1.11")
        # For dev installs, it will be something like "1.1.11.post1.dev17+g27af3a7.d20250309"
        # Which is <tag>.post<postN>.dev<devN>+g<git commit hash>.d<YYYYMMDD>
        # <postN> is the number of local commits since the checkout commit
        # <devN> is the number of commits since the last tag
        raw_version = __version__

        # Format the version string to our desired format
        if "+" in raw_version:
            version_part, git_date_part = raw_version.split("+", 1)

            # Get just the git commit hash
            commit_hash = (
                git_date_part[1:].split(".", 1)[0]
                if git_date_part.startswith("g")
                else git_date_part.split(".", 1)[0]
            )

            # Remove .dev component (from "no-guess-dev" scheme)
            clean_version = version_part
            if ".dev" in clean_version:
                clean_version = clean_version.split(".dev")[0]

            # Apply dirty status (from "no-guess-dev" scheme)
            if ".post" in clean_version:
                base = clean_version.split(".post")[0]
                version_str = f"{base}-{commit_hash}-dirty"
            else:
                version_str = f"{clean_version}-{commit_hash}"
        else:
            version_str = raw_version

        click.echo(f"warnet version {version_str}")
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
