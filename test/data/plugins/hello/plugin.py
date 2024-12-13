#!/usr/bin/env python3
import json
import logging
from pathlib import Path
from typing import Optional

import click
from kubernetes.stream import stream

from warnet.constants import PLUGIN_ANNEX, AnnexMember, HookValue, WarnetContent
from warnet.k8s import (
    get_default_namespace,
    get_static_client,
)
from warnet.process import run_command

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


@click.group()
@click.pass_context
def hello(ctx):
    """Commands for the Hello plugin"""
    ctx.ensure_object(dict)
    plugin_dir = Path(__file__).resolve().parent
    ctx.obj[PLUGIN_DIR_TAG] = Path(plugin_dir)


@hello.command()
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
        key: plugin_content.get(key) for key in ("podName", "helloTo") if plugin_content.get(key)
    }
    return data or None


def _launch_pod(
    ctx, install_name: str = "hello", podName: str = "hello-pod", helloTo: str = "World!"
):
    command = f"helm upgrade --install {install_name} {ctx.obj[PLUGIN_DIR_TAG]}/charts/hello --set podName={podName} --set helloTo={helloTo}"
    log.info(command)
    log.info(run_command(command))


def _sh(pod, method: str, params: tuple[str, ...]) -> str:
    namespace = get_default_namespace()

    sclient = get_static_client()
    if params:
        cmd = [method]
        cmd.extend(params)
    else:
        cmd = [method]
    try:
        resp = stream(
            sclient.connect_get_namespaced_pod_exec,
            pod,
            namespace,
            container=PRIMARY_CONTAINER,
            command=cmd,
            stderr=True,
            stdin=False,
            stdout=True,
            tty=False,
            _preload_content=False,
        )
        stdout = ""
        stderr = ""
        while resp.is_open():
            resp.update(timeout=1)
            if resp.peek_stdout():
                stdout_chunk = resp.read_stdout()
                stdout += stdout_chunk
            if resp.peek_stderr():
                stderr_chunk = resp.read_stderr()
                stderr += stderr_chunk
        return stdout + stderr
    except Exception as err:
        print(f"Could not execute stream: {err}")


@hello.command(context_settings={"ignore_unknown_options": True})
@click.argument("pod", type=str)
@click.argument("method", type=str)
@click.argument("params", type=str, nargs=-1)  # this will capture all remaining arguments
def sh(pod: str, method: str, params: tuple[str, ...]):
    """Run shell commands in a pod"""
    print(_sh(pod, method, params))


if __name__ == "__main__":
    hello()
