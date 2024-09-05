import click

from .admin import admin, auth
from .bitcoin import bitcoin
from .control import down, run, stop
from .deploy import deploy
from .graph import graph
from .image import image
from .project import create, init, setup
from .status import status


@click.group()
def cli():
    pass


cli.add_command(admin)
cli.add_command(auth)
cli.add_command(bitcoin)
cli.add_command(create)
cli.add_command(deploy)
cli.add_command(down)
cli.add_command(graph)
cli.add_command(image)
cli.add_command(init)
cli.add_command(run)
cli.add_command(setup)
cli.add_command(status)
cli.add_command(stop)


if __name__ == "__main__":
    cli()
