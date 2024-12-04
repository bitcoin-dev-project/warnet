import json
import logging
import time
from pathlib import Path
from subprocess import run
from time import sleep
from typing import Optional

import click
from kubernetes.stream import stream

# When we want to select pods based on their role in Warnet, we use "mission" tags. The "mission"
# tag for "lightning" nodes is stored in LIGHTNING_MISSION.
from warnet.constants import LIGHTNING_MISSION, USER_DIR_TAG
from warnet.k8s import (
    download,
    get_default_namespace,
    get_mission,
    get_static_client,
    wait_for_init,
    wait_for_pod,
    write_file_to_container,
)
from warnet.plugins import get_plugins_directory_or
from warnet.process import run_command
from warnet.status import _get_tank_status as network_status

# To make a "mission" tag for your plugin, declare it using the variable name MISSION. This will
# be read by the warnet log system and status system.
# This should match the pod's "mission" value in this plugin's associated helm file.
MISSION = "simln"

# Each pod we deploy should have a primary container. We make the name of that primary container
# explicit here using the variable name CONTAINER which Warnet uses internally in its log and status
# systems.
# Again, this should match the container name provided in the associated helm file.
CONTAINER = MISSION


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
# Each plugin must declare a click "group" by decorating a function named after the plugin.
# This makes your plugin available in the plugin section of Warnet.
@click.group()
def simln():
    """Commands for the SimLN plugin"""
    pass


# Make sure to register your plugin by adding the group function like so:
def warnet_register_plugin(register_command):
    register_command(simln)  # <-- We added the group function here.


# The group function name is then used in decorators to create commands. These commands are
# available to users when they access your plugin from the command line in Warnet.
@simln.command()
def run_demo():
    """Run the SimLN Plugin demo"""
    _init_network()
    _fund_wallets()
    _wait_for_all_ln_nodes_to_have_a_host()
    log.info(warnet("bitcoin rpc tank-0000 -generate 7"))
    manual_open_channels()
    log.info(warnet("bitcoin rpc tank-0000 -generate 7"))
    wait_for_gossip_sync(2)
    log.info("done waiting")
    pod_name = prepare_and_launch_activity()
    log.info(pod_name)
    wait_for_pod(pod_name, 60)


@simln.command()
def list_simln_podnames():
    """Get a list of simln pod names"""
    print([pod.metadata.name for pod in get_mission(MISSION)])


@simln.command()
@click.argument("pod_name", type=str)
def download_results(pod_name: str):
    """Download SimLN results to the current directory"""
    dest = download(pod_name, source_path=Path("/working/results"))
    print(f"Downloaded results to: {dest}")


def prepare_and_launch_activity() -> str:
    sample_activity = _get_example_activity()
    log.info(f"Activity: {sample_activity}")
    pod_name = _launch_activity(sample_activity)
    log.info("Sent command. Done.")
    return pod_name


# When we want to use a command inside our plugin and also provide that command to the user, we like
# to create a private function whose name starts with an underscore. We also make a public function
# with the same name except that we leave off the underscore, decorate it with the command
# decorator, and also provide an instructive doc string which Warnet will display in the help
# section of the command line program.
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


def _launch_activity(activity: list[dict], user_dir: Optional[str] = None) -> str:
    """Launch a SimLN chart which includes the `activity`"""
    plugin_dir = get_plugins_directory_or(user_dir)

    timestamp = int(time.time())
    name = f"simln-{timestamp}"

    command = f"helm upgrade --install {timestamp} {plugin_dir}/simln/charts/simln"
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
    user_dir = ctx.obj.get(USER_DIR_TAG)
    print(_launch_activity(parsed_activity, user_dir))


def _init_network():
    """Mine regtest coins and wait for ln nodes to come online."""
    log.info("Initializing network")
    wait_for_all_tanks_status(target="running")

    warnet("bitcoin rpc tank-0000 createwallet miner")
    warnet("bitcoin rpc tank-0000 -generate 110")
    wait_for_predicate(lambda: int(warnet("bitcoin rpc tank-0000 getblockcount")) > 100)

    def wait_for_all_ln_rpc():
        lns = get_mission(LIGHTNING_MISSION)
        for v1_pod in lns:
            ln = v1_pod.metadata.name
            try:
                warnet(f"ln rpc {ln} getinfo")
            except Exception:
                log.info(f"LN node {ln} not ready for rpc yet")
                return False
        return True

    wait_for_predicate(wait_for_all_ln_rpc)


@simln.command()
def init_network():
    """Initialize the demo network."""
    _init_network()


def _fund_wallets():
    """Fund each ln node with 10 regtest coins."""
    log.info("Funding wallets")
    outputs = ""
    lns = get_mission(LIGHTNING_MISSION)
    for v1_pod in lns:
        lnd = v1_pod.metadata.name
        addr = json.loads(warnet(f"ln rpc {lnd} newaddress p2wkh"))["address"]
        outputs += f',"{addr}":10'
    # trim first comma
    outputs = outputs[1:]
    log.info(warnet("bitcoin rpc tank-0000 sendmany '' '{" + outputs + "}'"))
    log.info(warnet("bitcoin rpc tank-0000 -generate 1"))


@simln.command()
def fund_wallets():
    """Fund each ln node with 10 regtest coins."""
    _fund_wallets()


def all_ln_nodes_have_a_host() -> bool:
    """Find out if each ln node has a host."""
    pods = get_mission(LIGHTNING_MISSION)
    host_havers = 0
    for pod in pods:
        name = pod.metadata.name
        result = warnet(f"ln host {name}")
        if len(result) > 1:
            host_havers += 1
    return host_havers == len(pods) and host_havers != 0


@simln.command()
def wait_for_all_ln_nodes_to_have_a_host():
    log.info(_wait_for_all_ln_nodes_to_have_a_host())


def _wait_for_all_ln_nodes_to_have_a_host():
    wait_for_predicate(all_ln_nodes_have_a_host, timeout=10 * 60)


def wait_for_predicate(predicate, timeout=5 * 60, interval=5):
    log.info(
        f"Waiting for predicate ({predicate.__name__}) with timeout {timeout}s and interval {interval}s"
    )
    while timeout > 0:
        try:
            if predicate():
                return
        except Exception:
            pass
        sleep(interval)
        timeout -= interval
    import inspect

    raise Exception(
        f"Timed out waiting for Truth from predicate: {inspect.getsource(predicate).strip()}"
    )


def wait_for_all_tanks_status(target: str = "running", timeout: int = 20 * 60, interval: int = 5):
    """Poll the warnet server for container status. Block until all tanks are running"""

    def check_status():
        tanks = network_status()
        stats = {"total": 0}
        # "Probably" means all tanks are stopped and deleted
        if len(tanks) == 0:
            return True
        for tank in tanks:
            status = tank["status"]
            stats["total"] += 1
            stats[status] = stats.get(status, 0) + 1
        log.info(f"Waiting for all tanks to reach '{target}': {stats}")
        return target in stats and stats[target] == stats["total"]

    wait_for_predicate(check_status, timeout, interval)


def wait_for_gossip_sync(expected: int = 2):
    """Wait for any of the ln nodes to have an `expected` number of edges."""
    log.info(f"Waiting for sync (expecting {expected})...")
    current = 0
    while current < expected:
        current = 0
        pods = get_mission(LIGHTNING_MISSION)
        for v1_pod in pods:
            node = v1_pod.metadata.name
            chs = json.loads(run_command(f"warnet ln rpc {node} describegraph"))["edges"]
            log.info(f"{node}: {len(chs)} channels")
            current += len(chs)
        sleep(1)
    log.info("Synced")


def warnet(cmd: str = "--help"):
    """Pass a `cmd` to Warnet."""
    log.info(f"Executing warnet command: {cmd}")
    command = ["warnet"] + cmd.split()
    proc = run(command, capture_output=True)
    if proc.stderr:
        raise Exception(proc.stderr.decode().strip())
    return proc.stdout.decode()


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


def manual_open_channels():
    """Manually open channels between ln nodes 1, 2, and 3"""

    def wait_for_two_txs():
        wait_for_predicate(
            lambda: json.loads(warnet("bitcoin rpc tank-0000 getmempoolinfo"))["size"] == 2
        )

    # 0 -> 1 -> 2
    pk1 = warnet("ln pubkey tank-0001-ln")
    pk2 = warnet("ln pubkey tank-0002-ln")
    log.info(f"pk1: {pk1}")
    log.info(f"pk2: {pk2}")

    host1 = ""
    host2 = ""

    while not host1 or not host2:
        if not host1:
            host1 = warnet("ln host tank-0001-ln")
        if not host2:
            host2 = warnet("ln host tank-0002-ln")
        sleep(1)

    print(
        warnet(
            f"ln rpc tank-0000-ln openchannel --node_key {pk1} --local_amt 100000 --connect {host1}"
        )
    )
    print(
        warnet(
            f"ln rpc tank-0001-ln openchannel --node_key {pk2} --local_amt 100000 --connect {host2}"
        )
    )

    wait_for_two_txs()

    warnet("bitcoin rpc tank-0000 -generate 10")


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
            container=CONTAINER,
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
    """Run commands on a pod"""
    print(_sh(pod, method, params))