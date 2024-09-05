import click

from .admin import admin
from .bitcoin import bitcoin
from .control import down, logs, run, snapshot, stop
from .dashboard import dashboard
from .deploy import deploy
from .graph import create, graph
from .image import image
from .project import init, new, setup
from .status import status
from .users import auth


@click.group()
def cli():
    pass


cli.add_command(admin)
cli.add_command(auth)
cli.add_command(bitcoin)
cli.add_command(deploy)
cli.add_command(down)
cli.add_command(dashboard)
cli.add_command(graph)
cli.add_command(image)
cli.add_command(init)
cli.add_command(logs)
cli.add_command(new)
cli.add_command(run)
cli.add_command(setup)
cli.add_command(snapshot)
cli.add_command(status)
cli.add_command(stop)
cli.add_command(create)


if __name__ == "__main__":
    cli()
