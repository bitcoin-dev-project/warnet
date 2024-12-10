#!/usr/bin/env python3

import json
import logging
import time
from pathlib import Path

import click
from kubernetes.stream import stream

# When we want to select pods based on their role in Warnet, we use "mission" tags. The "mission"
# tag for "lightning" nodes is stored in LIGHTNING_MISSION.
from warnet.constants import LIGHTNING_MISSION
from warnet.k8s import (
    download,
    get_default_namespace,
    get_mission,
    get_static_client,
    wait_for_init,
    write_file_to_container,
)
from warnet.process import run_command

# Tt is common for Warnet objects to have a "mission" tag to query them in the cluster.
# To make a "mission" tag for your plugin, declare it using the variable name MISSION. This will
# be read by the warnet log system and status system.
# This must match the pod's "mission" value in the plugin's associated helm file.
MISSION = "simln"
PRIMARY_CONTAINER = MISSION

PLUGIN_DIR_TAG = "plugin_dir"


class SimLNError(Exception):
    pass


log = logging.getLogger(MISSION)
log.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
console_handler.setFormatter(formatter)
log.addHandler(console_handler)


# Warnet uses a python package called "click" to manage terminal interactions with the user.
# To use click, we must declare a click "group" by decorating a function named after the plugin.
# Using click makes it easy for users to interact with your plugin.
@click.group()
@click.pass_context
def simln(ctx):
    """Commands for the SimLN plugin"""
    ctx.ensure_object(dict)
    plugin_dir = Path(__file__).resolve().parent
    ctx.obj[PLUGIN_DIR_TAG] = Path(plugin_dir)


# The group name is then used in decorators to create commands. These commands are
# available to users when they access your plugin from the command line.
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


# When we want to use a command inside our plugin and also provide that command to the user, it
# helps to create a private function whose name starts with an underscore. We also make a public
# function with the same name except that we leave off the underscore, decorate it with the command
# decorator, and also provide an instructive doc string for the user.
def _get_example_activity() -> list[dict]:
    pods = get_mission(LIGHTNING_MISSION)
    try:
        pod_a = pods[1].metadata.name
        pod_b = pods[2].metadata.name
    except Exception as err:
        raise SimLNError(
            "Could not access the lightning nodes needed for the example.\n Try deploying some."
        ) from err
    return [{"source": pod_a, "destination": pod_b, "interval_secs": 1, "amount_msat": 2000}]


# Notice how the command that we make available to the user simply calls our internal command.
@simln.command()
def get_example_activity():
    """Get an activity representing node 2 sending msat to node 3"""
    print(json.dumps(_get_example_activity()))


# Take note of how click expects us to explicitly declare command line arguments.
@simln.command()
@click.argument("activity", type=str)
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


def _launch_activity(activity: list[dict], plugin_dir: str) -> str:
    """Launch a SimLN chart which includes the `activity`"""
    timestamp = int(time.time())
    name = f"simln-{timestamp}"

    command = f"helm upgrade --install {timestamp} {plugin_dir}/charts/simln"
    run_command(command)

    activity_json = _generate_activity_json(activity)
    wait_for_init(name, namespace=get_default_namespace(), quiet=True)
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
        raise SimLNError(f"Could not write sim.json to the init container: {name}")


def _generate_activity_json(activity: list[dict]) -> str:
    nodes = []

    for i in get_mission(LIGHTNING_MISSION):
        name = i.metadata.name
        node = {
            "id": name,
            "address": f"https://{name}:10009",
            "macaroon": "/working/admin.macaroon",
            "cert": "/working/tls.cert",
        }
        nodes.append(node)

    data = {"nodes": nodes, "activity": activity}

    return json.dumps(data, indent=2)


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
