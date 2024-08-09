import sys

import click

from .image_build import build_image


@click.group(name="image")
def image():
    """Build a custom Warnet Bitcoin Core image"""


@image.command()
@click.option("--repo", required=True, type=str)
@click.option("--commit-sha", required=True, type=str)
@click.option("--registry", required=True, type=str)
@click.option(
    "--tags",
    required=True,
    type=str,
    help="Comma-separated list of full tags including image names",
)
@click.option("--build-args", required=False, type=str)
@click.option("--arches", required=False, type=str)
@click.option("--action", required=False, type=str, default="load")
def build(repo, commit_sha, registry, tags, build_args, arches, action):
    """
    Build bitcoind and bitcoin-cli from <repo> at <commit_sha> with the specified <tags>.
    Optionally deploy to remote registry using --action=push, otherwise image is loaded to local registry.
    """
    res = build_image(repo, commit_sha, registry, tags, build_args, arches, action)
    if not res:
        sys.exit(1)
