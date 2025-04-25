#!/usr/bin/env python3
import json
import logging
import time
from enum import Enum
from pathlib import Path
from typing import Optional

import click
from kubernetes.stream import stream

from warnet.constants import LIGHTNING_MISSION, PLUGIN_ANNEX, AnnexMember, HookValue, WarnetContent
from warnet.k8s import (
    copyfile,
    download,
    get_default_namespace,
    get_mission,
    get_static_client,
    wait_for_init,
    write_file_to_container,
)
from warnet.process import run_command

MISSION = "simln"
PRIMARY_CONTAINER = MISSION

PLUGIN_DIR_TAG = "plugin_dir"


class PluginError(Exception):
    pass


log = logging.getLogger(MISSION)
log.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
console_handler.setFormatter(formatter)
log.addHandler(console_handler)


class PluginContent(Enum):
    ACTIVITY = "activity"


@click.group()
@click.pass_context
def simln(ctx):
    """Commands for the SimLN plugin"""
    ctx.ensure_object(dict)
    plugin_dir = Path(__file__).resolve().parent
    ctx.obj[PLUGIN_DIR_TAG] = Path(plugin_dir)


@simln.command()
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
    # write your plugin startup commands here
    activity = plugin_content.get(PluginContent.ACTIVITY.value)
    if activity:
        activity = json.loads(activity)
        print(activity)
    _launch_activity(activity, ctx.obj.get(PLUGIN_DIR_TAG))


@simln.command()
def list_pod_names():
    """Get a list of SimLN pod names"""
    print([pod.metadata.name for pod in get_mission(MISSION)])


@simln.command()
@click.argument("pod_name", type=str)
def download_results(pod_name: str):
    """Download SimLN results to the current directory"""
    dest = download(pod_name, source_path=Path("/working/results"))
    print(f"Downloaded results to: {dest}")


def _get_example_activity() -> list[dict]:
    pods = get_mission(LIGHTNING_MISSION)
    try:
        pod_a = pods[1].metadata.name
        pod_b = pods[2].metadata.name
    except Exception as err:
        raise PluginError(
            "Could not access the lightning nodes needed for the example.\n Try deploying some."
        ) from err
    return [{"source": pod_a, "destination": pod_b, "interval_secs": 1, "amount_msat": 2000}]


@simln.command()
def get_example_activity():
    """Get an activity representing node 2 sending msat to node 3"""
    print(json.dumps(_get_example_activity()))


@simln.command()
@click.argument(PluginContent.ACTIVITY.value, type=str)
@click.pass_context
def launch_activity(ctx, activity: str):
    """Deploys a SimLN Activity which is a JSON list of objects"""
    try:
        parsed_activity = json.loads(activity)
    except json.JSONDecodeError:
        log.error("Invalid JSON input for activity.")
        raise click.BadArgumentUsage("Activity must be a valid JSON string.") from None
    plugin_dir = ctx.obj.get(PLUGIN_DIR_TAG)
    print(_launch_activity(parsed_activity, plugin_dir))


def _launch_activity(activity: Optional[list[dict]], plugin_dir: str) -> str:
    """Launch a SimLN chart which optionally includes the `activity`"""
    timestamp = int(time.time())
    name = f"simln-{timestamp}"

    command = f"helm upgrade --install {timestamp} {plugin_dir}/charts/simln"

    run_command(command)
    activity_json = _generate_activity_json(activity)
    wait_for_init(name, namespace=get_default_namespace(), quiet=True)

    # write cert files to container
    transfer_cln_certs(name)
    if write_file_to_container(
        name,
        "init",
        "/working/sim.json",
        activity_json,
        namespace=get_default_namespace(),
        quiet=True,
    ):
        return name
    else:
        raise PluginError(f"Could not write sim.json to the init container: {name}")


def _generate_activity_json(activity: Optional[list[dict]]) -> str:
    nodes = []

    for i in get_mission(LIGHTNING_MISSION):
        ln_name = i.metadata.name
        port = 10009
        node = {"id": ln_name}
        if "cln" in i.metadata.labels["app.kubernetes.io/name"]:
            port = 9736
            node["ca_cert"] = f"/working/{ln_name}-ca.pem"
            node["client_cert"] = f"/working/{ln_name}-client.pem"
            node["client_key"] = f"/working/{ln_name}-client-key.pem"
        else:
            node["macaroon"] = "/working/admin.macaroon"
            node["cert"] = "/working/tls.cert"
        node["address"] = f"https://{ln_name}:{port}"
        nodes.append(node)

    if activity:
        data = {"nodes": nodes, PluginContent.ACTIVITY.value: activity}
    else:
        data = {"nodes": nodes}

    return json.dumps(data, indent=2)


def transfer_cln_certs(name):
    dst_container = "init"
    for i in get_mission(LIGHTNING_MISSION):
        ln_name = i.metadata.name
        if "cln" in i.metadata.labels["app.kubernetes.io/name"]:
            chain = i.metadata.labels["chain"]
            cln_root = f"/root/.lightning/{chain}"
            copyfile(
                ln_name,
                "cln",
                f"{cln_root}/ca.pem",
                name,
                dst_container,
                f"/working/{ln_name}-ca.pem",
            )
            copyfile(
                ln_name,
                "cln",
                f"{cln_root}/client.pem",
                name,
                dst_container,
                f"/working/{ln_name}-client.pem",
            )
            copyfile(
                ln_name,
                "cln",
                f"{cln_root}/client-key.pem",
                name,
                dst_container,
                f"/working/{ln_name}-client-key.pem",
            )


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


@simln.command(context_settings={"ignore_unknown_options": True})
@click.argument("pod", type=str)
@click.argument("method", type=str)
@click.argument("params", type=str, nargs=-1)  # this will capture all remaining arguments
def sh(pod: str, method: str, params: tuple[str, ...]):
    """Run shell commands in a pod"""
    print(_sh(pod, method, params))


if __name__ == "__main__":
    simln()
