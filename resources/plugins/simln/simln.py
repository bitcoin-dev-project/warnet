import json
import logging
import random
from pathlib import Path
from subprocess import run
from time import sleep

import click
from kubernetes.stream import stream

from warnet.k8s import (
    download,
    get_default_namespace,
    get_pods_with_label,
    get_static_client,
    wait_for_pod,
)
from warnet.plugins import _get_plugins_directory as get_plugin_directory
from warnet.process import run_command
from warnet.status import _get_tank_status as network_status

log = logging.getLogger("simln")
log.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
console_handler.setFormatter(formatter)
log.addHandler(console_handler)

LIGHTNING_SELECTOR = "mission=lightning"


@click.group()
def simln():
    """Commands for the SimLN plugin"""
    pass


def warnet_register_plugin(register_command):
    register_command(simln)


class SimLNError(Exception):
    pass


@simln.command()
def run_demo():
    """Run the SimLN Plugin demo"""
    _init_network()
    _fund_wallets()
    _wait_for_everyone_to_have_a_host()
    log.info(warnet("bitcoin rpc tank-0000 -generate 7"))
    # warnet("ln open-all-channels")
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
    print([pod.metadata.name for pod in get_pods_with_label("mission=simln")])


@simln.command()
def download_results(pod_name: str):
    """Download SimLN results to the current directory"""
    print(download(pod_name, source_path=Path("/working/results")))


def prepare_and_launch_activity() -> str:
    sample_activity = _get_example_activity()
    log.info(f"Activity: {sample_activity}")
    pod_name = _launch_activity(sample_activity)
    log.info("Sent command. Done.")
    return pod_name


def _get_example_activity() -> list[dict]:
    pods = get_pods_with_label(LIGHTNING_SELECTOR)
    try:
        pod_a = pods[1].metadata.name
        pod_b = pods[2].metadata.name
    except Exception as err:
        raise SimLNError(
            "Could not access the lightning nodes needed for the example.\n Try deploying some."
        ) from err
    return [{"source": pod_a, "destination": pod_b, "interval_secs": 1, "amount_msat": 2000}]


@simln.command()
def get_example_activity():
    """Get an activity representing node 2 sending msat to node 3"""
    print(_get_example_activity())


def _launch_activity(activity: list[dict]) -> str:
    """Launch a SimLN chart which includes the `activity`"""
    random_digits = "".join(random.choices("0123456789", k=10))
    plugin_dir = get_plugin_directory()
    _generate_nodes_file(activity, plugin_dir / Path("simln/charts/simln/files/sim.json"))
    command = f"helm upgrade --install simln-{random_digits} {plugin_dir}/simln/charts/simln"
    log.info(f"generate activity: {command}")
    run_command(command)
    return f"simln-simln-{random_digits}"


@simln.command()
@click.argument("activity", type=str)
def launch_activity(activity: str):
    """Takes a SimLN Activity which is a JSON list of objects."""
    parsed_activity = json.loads(activity)
    print(_launch_activity(parsed_activity))


def _init_network():
    """Mine regtest coins and wait for ln nodes to come online."""
    log.info("Initializing network")
    wait_for_all_tanks_status(target="running")

    warnet("bitcoin rpc tank-0000 createwallet miner")
    warnet("bitcoin rpc tank-0000 -generate 110")
    _wait_for_predicate(lambda: int(warnet("bitcoin rpc tank-0000 getblockcount")) > 100)

    def wait_for_all_ln_rpc():
        lns = get_pods_with_label(LIGHTNING_SELECTOR)
        for v1_pod in lns:
            ln = v1_pod.metadata.name
            try:
                warnet(f"ln rpc {ln} getinfo")
            except Exception:
                log.info(f"LN node {ln} not ready for rpc yet")
                return False
        return True

    _wait_for_predicate(wait_for_all_ln_rpc)


@simln.command()
def init_network():
    _init_network()


def _fund_wallets():
    """Fund each ln node with 10 regtest coins."""
    log.info("Funding wallets")
    outputs = ""
    lns = get_pods_with_label(LIGHTNING_SELECTOR)
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


def _everyone_has_a_host() -> bool:
    """Find out if each ln node has a host."""
    pods = get_pods_with_label(LIGHTNING_SELECTOR)
    host_havers = 0
    for pod in pods:
        name = pod.metadata.name
        result = warnet(f"ln host {name}")
        if len(result) > 1:
            host_havers += 1
    return host_havers == len(pods) and host_havers != 0


@simln.command()
def wait_for_everyone_to_have_a_host():
    log.info(_wait_for_everyone_to_have_a_host())


def _wait_for_everyone_to_have_a_host():
    _wait_for_predicate(_everyone_has_a_host, timeout=10 * 60)


def _wait_for_predicate(predicate, timeout=5 * 60, interval=5):
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

    _wait_for_predicate(check_status, timeout, interval)


def wait_for_gossip_sync(expected: int = 2):
    """Wait for any of the ln nodes to have an `expected` number of edges."""
    log.info(f"Waiting for sync (expecting {expected})...")
    current = 0
    while current < expected:
        current = 0
        pods = get_pods_with_label(LIGHTNING_SELECTOR)
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


def _generate_nodes_file(activity: list[dict], output_file: Path = Path("nodes.json")):
    nodes = []

    for i in get_pods_with_label(LIGHTNING_SELECTOR):
        name = i.metadata.name
        node = {
            "id": name,
            "address": f"https://{name}:10009",
            "macaroon": "/working/admin.macaroon",
            "cert": "/working/tls.cert",
        }
        nodes.append(node)

    data = {"nodes": nodes, "activity": activity}

    with open(output_file, "w") as f:
        json.dump(data, f, indent=2)


def manual_open_channels():
    """Manually open channels between ln nodes 1, 2, and 3"""

    def wait_for_two_txs():
        _wait_for_predicate(
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


def _rpc(pod, method: str, params: tuple[str, ...]) -> str:
    namespace = get_default_namespace()

    sclient = get_static_client()
    if params:
        cmd = [method]
        cmd.extend(params)
    else:
        cmd = [method]
    resp = stream(
        sclient.connect_get_namespaced_pod_exec,
        pod,
        namespace,
        container="simln",
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


@simln.command(context_settings={"ignore_unknown_options": True})
@click.argument("pod", type=str)
@click.argument("method", type=str)
@click.argument("params", type=str, nargs=-1)  # this will capture all remaining arguments
def rpc(pod: str, method: str, params: tuple[str, ...]):
    """Run commands on a pod"""
    print(_rpc(pod, method, params))
