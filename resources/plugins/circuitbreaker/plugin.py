#!/usr/bin/env python3
import json
import logging
from enum import Enum
from pathlib import Path
import time
from typing import Optional

import click

from warnet.constants import PLUGIN_ANNEX, AnnexMember, HookValue, WarnetContent
from warnet.process import run_command

from warnet.k8s import (
    download,
    get_default_namespace,
    get_mission,
    get_static_client,
    wait_for_init,
    write_file_to_container,
)

MISSION = "circuitbreaker"
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

class PluginContent(Enum):
    MODE = "mode"
    MAX_PENDING_HTLCS = "maxPendingHtlcs"
    RATE_LIMIT = "rateLimit"

@click.group()
@click.pass_context
def circuitbreaker(ctx):
    """Commands for the Circuit Breaker plugin"""
    ctx.ensure_object(dict)
    plugin_dir = Path(__file__).resolve().parent
    ctx.obj[PLUGIN_DIR_TAG] = Path(plugin_dir)


@circuitbreaker.command()
@click.argument("plugin_content", type=str)
@click.argument("warnet_content", type=str)
@click.pass_context
def entrypoint(ctx, plugin_content: str, warnet_content: str):
    """Plugin entrypoint"""
    plugin_content: dict = json.loads(plugin_content)
    warnet_content: dict = json.loads(warnet_content)

    hook_value = warnet_content.get(WarnetContent.HOOK_VALUE.value)

    assert hook_value in {
        item.value for item in HookValue
    }, f"{hook_value} is not a valid HookValue"

    if warnet_content.get(PLUGIN_ANNEX):
        for annex_member in [annex_item for annex_item in warnet_content.get(PLUGIN_ANNEX)]:
            assert annex_member in {
                item.value for item in AnnexMember
            }, f"{annex_member} is not a valid AnnexMember"

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
                _launch_circuit_breaker(ctx, node_name=hook_value.value.lower()+"breaker",hook_value=hook_value.value)
            else:
                _launch_circuit_breaker(ctx, node_name=hook_value.value.lower()+"breaker",hook_value=hook_value.value)
        case HookValue.PRE_NODE:
            name = warnet_content[PLUGIN_ANNEX][AnnexMember.NODE_NAME.value] + "-pre-pod"
            _launch_circuit_breaker(ctx, node_name=hook_value.value.lower() + "-" + name, hook_value=hook_value.value)
        case HookValue.POST_NODE:
            name = warnet_content[PLUGIN_ANNEX][AnnexMember.NODE_NAME.value] + "-post-pod"
            _launch_circuit_breaker(ctx, node_name=hook_value.value.lower() + "-" + name, hook_value=hook_value.value)
            
def get_data(plugin_content: dict) -> Optional[dict]:
    data = {
        key: plugin_content.get(key)
        for key in (PluginContent.MAX_PENDING_HTLCS.value, PluginContent.RATE_LIMIT.value)
        if plugin_content.get(key)
    }
    return data or None


def _launch_circuit_breaker(ctx, node_name: str, hook_value: str):
    timestamp = int(time.time())
    release_name = f"cb-{node_name}"
    
    # command = f"helm upgrade --install {release_name} {ctx.obj[PLUGIN_DIR_TAG]}/charts/circuitbreaker"
    command = (
        f"helm upgrade --install {release_name} {ctx.obj[PLUGIN_DIR_TAG]}/charts/circuitbreaker "
        f"--set name={release_name}"
    )
    log.info(command)
    run_command(command)
    
    if(hook_value==HookValue.POST_DEPLOY):
        wait_for_init(release_name, namespace=get_default_namespace(), quiet=True)


if __name__ == "__main__":
    circuitbreaker()
