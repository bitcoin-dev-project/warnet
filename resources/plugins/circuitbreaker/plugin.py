#!/usr/bin/env python3
import json
import logging
from enum import Enum
from pathlib import Path
import subprocess
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
    POD_NAME = "podName"
    LND_RPC_SERVER = "rpcserver"
    HTTP_LISTEN = "httplisten"

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
        case HookValue.POST_DEPLOY:
            data = get_data(plugin_content)
            if data:
                _launch_pod(ctx, install_name="circuitbreaker", **data)
            else:
                _launch_pod(ctx, install_name="circuitbreaker")
        case _:
            log.info(f"No action required for hook {hook_value}")
            
def get_data(plugin_content: dict) -> Optional[dict]:
    data = {
        key: plugin_content.get(key)
        for key in (PluginContent.POD_NAME.value, PluginContent.LND_RPC_SERVER.value, PluginContent.HTTP_LISTEN.value)
        if plugin_content.get(key)
    }
    return data or None

# def _create_secrets():
#     """Use local LND files for testing"""
#     log.info("Using local LND files for testing")
#     tls_cert_path = Path.home() / ".lnd" / "tls.cert"
#     admin_macaroon_path = Path.home() / ".lnd" / "data" / "chain" / "bitcoin" / "signet" / "admin.macaroon"

#     if not tls_cert_path.exists():
#         raise PluginError(f"TLS certificate not found at {tls_cert_path}")
#     if not admin_macaroon_path.exists():
#         raise PluginError(f"Admin macaroon not found at {admin_macaroon_path}")

#     log.info(f"Using TLS certificate: {tls_cert_path}")
#     log.info(f"Using admin macaroon: {admin_macaroon_path}")
    
# def _create_secrets():
#     """Create Kubernetes secrets for each LND node"""
#     lnd_pods = subprocess.check_output(["kubectl", "get", "pods", "-l", "mission=lightning", "-o", "name"]).decode().splitlines()
#     # lnd_pods = subprocess.check_output(["kubectl", "get", "pods", "-l", "app=warnet", "-l", "mission=lightning", "-o", "name"]).decode().splitlines()
#     for node in lnd_pods:
#         node_name = node.split('/')[-1]
#         log.info(f"Waiting for {node_name} to be ready...")
#         wait_for_init(node_name, namespace=get_default_namespace(), quiet=True)
#         log.info(f"Creating secrets for {node_name}")
#         subprocess.run(["kubectl", "cp", f"{node}:/root/.lnd/tls.cert", "./tls.cert"], check=True)
#         subprocess.run(["kubectl", "cp", f"{node}:/root/.lnd/data/chain/bitcoin/regtest/admin.macaroon", "./admin.macaroon"], check=True)
#         subprocess.run(["kubectl", "create", "secret", "generic", f"lnd-tls-cert-{node_name}", "--from-file=tls.cert=./tls.cert"], check=True)
#         subprocess.run(["kubectl", "create", "secret", "generic", f"lnd-macaroon-{node_name}", "--from-file=admin.macaroon=./admin.macaroon"], check=True)
        
def _create_secrets():
    """Create Kubernetes secrets for each LND node"""
    lnd_pods = subprocess.check_output(
        ["kubectl", "get", "pods", "-l", "mission=lightning", "-o", "name"]
    ).decode().splitlines()

    for node in lnd_pods:
        node_name = node.split('/')[-1]
        log.info(f"Waiting for {node_name} to be ready...")

        # Wait for the pod to be ready
        max_retries = 10
        retry_delay = 10  # seconds
        for attempt in range(max_retries):
            try:
                # Check if the pod is ready
                pod_status = subprocess.check_output(
                    ["kubectl", "get", "pod", node_name, "-o", "jsonpath='{.status.phase}'"]
                ).decode().strip("'")

                if pod_status == "Running":
                    log.info(f"{node_name} is ready.")
                    break
                else:
                    log.info(f"{node_name} is not ready yet (status: {pod_status}). Retrying in {retry_delay} seconds...")
            except subprocess.CalledProcessError as e:
                log.error(f"Failed to check pod status for {node_name}: {e}")
                if attempt == max_retries - 1:
                    raise PluginError(f"Pod {node_name} did not become ready after {max_retries} attempts.")

            time.sleep(retry_delay)

        # Create secrets for the pod
        log.info(f"Creating secrets for {node_name}")
        try:
            subprocess.run(
                ["kubectl", "cp", f"{node_name}:/root/.lnd/tls.cert", "./tls.cert"],
                check=True
            )
            subprocess.run(
                ["kubectl", "cp", f"{node_name}:/root/.lnd/data/chain/bitcoin/regtest/admin.macaroon", "./admin.macaroon"],
                check=True
            )
            subprocess.run(
                ["kubectl", "create", "secret", "generic", f"lnd-tls-cert-{node_name}", "--from-file=tls.cert=./tls.cert"],
                check=True
            )
            subprocess.run(
                ["kubectl", "create", "secret", "generic", f"lnd-macaroon-{node_name}", "--from-file=admin.macaroon=./admin.macaroon"],
                check=True
            )
        except subprocess.CalledProcessError as e:
            log.error(f"Failed to create secrets for {node_name}: {e}")
            raise PluginError(f"Failed to create secrets for {node_name}.")

def _launch_pod(ctx,
                install_name: str = "circuitbreaker", 
                podName: str = "circuitbreaker-pod", 
                rpcserver: str = "localhost:10009", 
                httplisten: str = "0.0.0.0:9235"):
    timestamp = int(time.time())
    # release_name = f"cb-{install_name}"
    
    command = (
        f"helm upgrade --install {install_name} {ctx.obj[PLUGIN_DIR_TAG]}/charts/circuitbreaker "
        f"--set podName={podName} --set rpcserver={rpcserver} --set httplisten={httplisten}"
    )
    
    log.info(command)
    log.info(run_command(command))

if __name__ == "__main__":
    circuitbreaker()
