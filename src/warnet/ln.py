import json
from typing import Optional

import click

from .k8s import (
    get_default_namespace_or,
    get_pod,
)
from .process import run_command


@click.group(name="ln")
def ln():
    """Control running lightning nodes"""


@ln.command(context_settings={"ignore_unknown_options": True})
@click.argument("pod", type=str)
@click.argument("method", type=str)
@click.argument("params", type=str, nargs=-1)  # this will capture all remaining arguments
@click.option("--namespace", default=None, show_default=True)
def rpc(pod: str, method: str, params: str, namespace: Optional[str]):
    """
    Call lightning cli rpc <command> on <ln pod name>
    """
    print(_rpc(pod, method, params, namespace))


def _rpc(pod_name: str, method: str, params: str = "", namespace: Optional[str] = None):
    pod = get_pod(pod_name)
    namespace = get_default_namespace_or(namespace)
    chain = pod.metadata.labels["chain"]
    cmd = f"kubectl -n {namespace} exec {pod_name} -- lncli --network {chain} {method} {' '.join(map(str, params))}"
    return run_command(cmd)


@ln.command()
@click.argument("pod", type=str)
def pubkey(
    pod: str,
):
    """
    Get lightning node pub key from <ln pod name>
    """
    print(_pubkey(pod))


def _pubkey(pod: str):
    info = _rpc(pod, "getinfo")
    return json.loads(info)["identity_pubkey"]


@ln.command()
@click.argument("pod", type=str)
def host(
    pod: str,
):
    """
    Get lightning node host from <ln pod name>
    """
    print(_host(pod))


def _host(pod):
    info = _rpc(pod, "getinfo")
    uris = json.loads(info)["uris"]
    if uris and len(uris) >= 0:
        return uris[0].split("@")[1]
    else:
        return ""
