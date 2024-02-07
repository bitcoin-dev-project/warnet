import sys

import click

from .image_build import build_image


@click.group(name="image")
def image():
    """Compile and deploy a custom version of bitcoin core to a docker image registry"""


@image.command()
@click.option("--repo", required=True, type=str)
@click.option("--branch", required=True, type=str)
@click.option("--registry", required=True, type=str)
@click.option("--tag", required=True, type=str)
@click.option("--build-args", required=False, type=str)
@click.option("--arches", required=False, type=str)
@click.option("--action", required=False, type=str)
def build(repo, branch, registry, tag, build_args, arches, action="load"):
    """
    Build bitcoind and bitcoin-cli from <repo>/<branch> as <registry>:<tag>.
    Optionally deploy to remote registry using --action=push, otherwise image is loaded to local registry.
    """
    res = build_image(repo, branch, registry, tag, build_args, arches, action)
    if not res:
        sys.exit(1)
