from pathlib import Path

import click

from warnet.constants import USER_DIR_TAG

from .admin import admin
from .bitcoin import bitcoin
from .control import down, logs, run, snapshot, stop
from .dashboard import dashboard
from .deploy import deploy
from .graph import create, graph, import_network
from .image import image
from .ln import ln
from .plugins import load_plugins, load_user_modules, plugins
from .project import init, new, setup
from .status import status
from .users import auth


@click.group()
@click.option(
    "--user-dir",
    type=click.Path(exists=True, file_okay=False),
    help="Path to the user's Warnet project directory.",
)
@click.pass_context
def cli(ctx, user_dir: str):
    ctx.ensure_object(dict)  # initialize ctx object
    if user_dir:
        ctx.obj[USER_DIR_TAG] = Path(user_dir)
    if load_user_modules(ctx.obj.get(USER_DIR_TAG)):
        load_plugins()
    pass


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
cli.add_command(plugins)


if __name__ == "__main__":
    cli()
