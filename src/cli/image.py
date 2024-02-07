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
def build(repo, branch, registry, tag, build_args, arches):
    """
    Build bitcoind and bitcoin-cli from <repo>/<branch> and deploy to <registry> as <tag>
    This requires docker and buildkit to be enabled.
    """
    res = build_and_upload_images(repo, branch, registry, tag, build_args, arches)
    if not res:
        sys.exit(1)
