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
    ln_client = f"lncli --network {chain}"
    if "cln" in pod.metadata.labels["app.kubernetes.io/name"]:
        ln_client = "lightning-cli"
    elif "eclair" in pod.metadata.labels["app.kubernetes.io/name"]:
        ln_client = "eclair-cli -p 21satoshi"
    cmd = f"kubectl -n {namespace} exec {pod_name} -- {ln_client} {method} {' '.join(map(str, params))}"
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


def _pubkey(pod_name: str):
    info = _rpc(pod_name, "getinfo")
    pod = get_pod(pod_name)
    pubkey_key = "identity_pubkey"
    if "cln" in pod.metadata.labels["app.kubernetes.io/name"]:
        pubkey_key = "id"
    elif "eclair" in pod.metadata.labels["app.kubernetes.io/name"]:
        pubkey_key = "nodeId"
    return json.loads(info)[pubkey_key]


@ln.command()
@click.argument("pod", type=str)
def host(
    pod: str,
):
    """
    Get lightning node host from <ln pod name>
    """
    print(_host(pod))


def _host(pod_name: str):
    info = _rpc(pod_name, "getinfo")
    pod = get_pod(pod_name)
    if (
        "cln" in pod.metadata.labels["app.kubernetes.io/name"]
        or "eclair" in pod.metadata.labels["app.kubernetes.io/name"]
    ):
        return json.loads(info)["alias"]
    else:
        uris = json.loads(info)["uris"]
        if uris and len(uris) >= 0:
            return uris[0].split("@")[1]
        else:
            return ""
