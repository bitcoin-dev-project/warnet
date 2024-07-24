import os
import subprocess
from importlib import resources

import click
from rich import print as richprint

from .bitcoin import bitcoin
from .cluster import cluster
from .graph import graph
from .image import image
from .ln import ln
from .network import network
from .scenarios import scenarios


@click.group()
def cli():
    pass


cli.add_command(bitcoin)
cli.add_command(cluster)
cli.add_command(graph)
cli.add_command(image)
cli.add_command(ln)
cli.add_command(network)
cli.add_command(scenarios)


@cli.command(name="help")
@click.argument("commands", required=False, nargs=-1)
@click.pass_context
def help_command(ctx, commands):
    """
    Display help information for the given [command] (and sub-command).
    If no command is given, display help for the main CLI.
    """
    if not commands:
        # Display help for the main CLI
        richprint(ctx.parent.get_help())
        return

    # Recurse down the subcommands, fetching the command object for each
    cmd_obj = cli
    for command in commands:
        cmd_obj = cmd_obj.get_command(ctx, command)
        if cmd_obj is None:
            richprint(f'Unknown command "{command}" in {commands}')
            return
        ctx = click.Context(cmd_obj, info_name=command, parent=ctx)

    if cmd_obj is None:
        richprint(f"Unknown command: {commands}")
        return

    # Get the help info
    help_info = cmd_obj.get_help(ctx).strip()
    # Get rid of the duplication
    help_info = help_info.replace("Usage: warcli help [COMMANDS]...", "Usage: warcli", 1)
    richprint(help_info)


cli.add_command(help_command)


@cli.command()
def setup():
    """Run the Warnet quick start setup script"""
    try:
        with resources.path("warnet.scripts", "quick_start.sh") as script_path:
            process = subprocess.Popen(
                ["/bin/bash", str(script_path)],
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


if __name__ == "__main__":
    cli()
