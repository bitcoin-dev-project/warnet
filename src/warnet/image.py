import sys

import click

from .image_build import build_image


@click.group(name="image")
def image():
    """Build a custom Warnet Bitcoin Core image"""


@image.command()
@click.option("--repo", required=True, type=str)
@click.option("--commit-sha", required=True, type=str)
@click.option(
    "--tags",
    required=True,
    type=str,
    help="Comma-separated list of full tags including image names",
)
@click.option("--build-args", required=False, type=str)
@click.option("--arches", required=False, type=str)
@click.option("--action", required=False, type=str, default="load")
def build(repo, commit_sha, tags, build_args, arches, action):
    """Build a Bitcoin Core Docker image with specified parameters.

    \b
    Usage Examples:
        # Build an image for Warnet repository
            warnet image build --repo bitcoin/bitcoin --commit-sha d6db87165c6dc2123a759c79ec236ea1ed90c0e3 --tags bitcoindevproject/bitcoin:v29.0-rc2 --arches amd64,arm64,armhf --action push
        # Build an image for local testing
            warnet image build --repo bitcoin/bitcoin --commit-sha d6db87165c6dc2123a759c79ec236ea1ed90c0e3 --tags bitcoindevproject/bitcoin:v29.0-rc2 --action load
    """
    res = build_image(repo, commit_sha, tags, build_args, arches, action)
    if not res:
        sys.exit(1)
