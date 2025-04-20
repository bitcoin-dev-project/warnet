#!/usr/bin/env python3
import json
import logging
from enum import Enum
from pathlib import Path
from typing import Optional

import click

from warnet.constants import PLUGIN_ANNEX, AnnexMember, HookValue, WarnetContent
from warnet.process import run_command

# It is common for Warnet objects to have a "mission" label to help query them in the cluster.
MISSION = "hello"
PRIMARY_CONTAINER = MISSION

PLUGIN_DIR_TAG = "plugin_dir"


class PluginError(Exception):
    pass


log = logging.getLogger(MISSION)
if not log.hasHandlers():
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    console_handler.setFormatter(formatter)
    log.addHandler(console_handler)
log.setLevel(logging.DEBUG)
log.propagate = True


# Plugins look like this in the `network.yaml` file:
#
# plugins:
#   hello:
#     podName: "a-pod-name"
#     helloTo: "World!"
#
# "podName" and "helloTo" are essentially dictionary keys, and it helps to keep those keys in an
# enum in order to prevent typos.
class PluginContent(Enum):
    POD_NAME = "podName"
    HELLO_TO = "helloTo"


# Warnet uses a python package called "click" to manage terminal interactions with the user.
# To use click, we must declare a click "group" by decorating a function named after the plugin.
# While optional, using click makes it easy for users to interact with your plugin.
@click.group()
@click.pass_context
def hello(ctx):
    """Commands for the Hello plugin"""
    ctx.ensure_object(dict)
    plugin_dir = Path(__file__).resolve().parent
    ctx.obj[PLUGIN_DIR_TAG] = Path(plugin_dir)


# Each Warnet plugin must have an entrypoint function which takes two JSON objects: plugin_content
# and warnet_content. We have seen the PluginContent enum above. Warnet also has a WarnetContent
# enum which holds the keys to the warnet_content dictionary.
@hello.command()
@click.argument("plugin_content", type=str)
@click.argument("warnet_content", type=str)
@click.pass_context
def entrypoint(ctx, plugin_content: str, warnet_content: str):
    """Plugin entrypoint"""
    plugin_content: dict = json.loads(plugin_content)
    warnet_content: dict = json.loads(warnet_content)

    hook_value = warnet_content.get(WarnetContent.HOOK_VALUE.value)

    assert hook_value in {item.value for item in HookValue}, (
        f"{hook_value} is not a valid HookValue"
    )

    if warnet_content.get(PLUGIN_ANNEX):
        for annex_member in [annex_item for annex_item in warnet_content.get(PLUGIN_ANNEX)]:
            assert annex_member in {item.value for item in AnnexMember}, (
                f"{annex_member} is not a valid AnnexMember"
            )

    warnet_content[WarnetContent.HOOK_VALUE.value] = HookValue(hook_value)

    _entrypoint(ctx, plugin_content, warnet_content)


def _entrypoint(ctx, plugin_content: dict, warnet_content: dict):
    """Called by entrypoint"""
    hook_value = warnet_content[WarnetContent.HOOK_VALUE.value]

    match hook_value:
        case (
            HookValue.PRE_NETWORK
            | HookValue.POST_NETWORK
            | HookValue.PRE_DEPLOY
            | HookValue.POST_DEPLOY
        ):
            data = get_data(plugin_content)
            if data:
                _launch_pod(ctx, install_name=hook_value.value.lower() + "-hello", **data)
            else:
                _launch_pod(ctx, install_name=hook_value.value.lower() + "-hello")
        case HookValue.PRE_NODE:
            name = warnet_content[PLUGIN_ANNEX][AnnexMember.NODE_NAME.value] + "-pre-hello-pod"
            _launch_pod(ctx, install_name=hook_value.value.lower() + "-" + name, podName=name)
        case HookValue.POST_NODE:
            name = warnet_content[PLUGIN_ANNEX][AnnexMember.NODE_NAME.value] + "-post-hello-pod"
            _launch_pod(ctx, install_name=hook_value.value.lower() + "-" + name, podName=name)


def get_data(plugin_content: dict) -> Optional[dict]:
    data = {
        key: plugin_content.get(key)
        for key in (PluginContent.POD_NAME.value, PluginContent.HELLO_TO.value)
        if plugin_content.get(key)
    }
    return data or None


def _launch_pod(
    ctx, install_name: str = "hello", podName: str = "hello-pod", helloTo: str = "World!"
):
    command = (
        f"helm upgrade --install {install_name} {ctx.obj[PLUGIN_DIR_TAG]}/charts/hello "
        f"--set podName={podName} --set helloTo={helloTo}"
    )
    log.info(command)
    log.info(run_command(command))


if __name__ == "__main__":
    hello()
