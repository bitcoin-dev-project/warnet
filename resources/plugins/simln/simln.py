import json
import logging
import random
from pathlib import Path
from subprocess import run
from time import sleep

from warnet.k8s import download, get_pods_with_label, wait_for_pod
from warnet.plugin import _get_plugin_directory as get_plugin_directory
from warnet.process import run_command
from warnet.status import _get_tank_status as network_status

log = logging.getLogger("simln")
log.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
console_handler.setFormatter(formatter)
log.addHandler(console_handler)

lightning_selector = "mission=lightning"


def run_simln():
    """Run a SimLN Plugin demo"""
    init_network()
    fund_wallets()
    wait_for_everyone_to_have_a_host()
    log.info(warnet("bitcoin rpc tank-0000 -generate 7"))
    # warnet("ln open-all-channels")
    manual_open_channels()
    log.info(warnet("bitcoin rpc tank-0000 -generate 7"))
    wait_for_gossip_sync(2)
    log.info("done waiting")
    pod_name = _prepare_and_launch_activity()
    log.info(pod_name)
    wait_for_pod(pod_name, 60)


def _prepare_and_launch_activity() -> str:
    sample_activity = get_example_activity()
    log.info(f"Activity: {sample_activity}")
    pod_name = launch_activity(sample_activity)
    log.info("Sent command. Done.")
    return pod_name


def get_example_activity() -> list[dict]:
    """Get an activity representing node 2 sending msat to node 3"""
    pods = get_pods_with_label(lightning_selector)
    pod_a = pods[1].metadata.name
    pod_b = pods[2].metadata.name
    return [{"source": pod_a, "destination": pod_b, "interval_secs": 1, "amount_msat": 2000}]


def launch_activity(activity: list[dict]) -> str:
    """Launch a SimLN chart which includes the `activity`"""
    random_digits = "".join(random.choices("0123456789", k=10))
    plugin_dir = get_plugin_directory()
    _generate_nodes_file(activity, plugin_dir / Path("simln/charts/simln/files/sim.json"))
    command = f"helm upgrade --install simln-{random_digits} {plugin_dir}/simln/charts/simln"
    log.info(f"generate activity: {command}")
    run_command(command)
    return f"simln-simln-{random_digits}"


def init_network():
    """Mine regtest coins and wait for ln nodes to come online."""
    log.info("Initializing network")
    wait_for_all_tanks_status(target="running")

    warnet("bitcoin rpc tank-0000 createwallet miner")
    warnet("bitcoin rpc tank-0000 -generate 110")
    _wait_for_predicate(lambda: int(warnet("bitcoin rpc tank-0000 getblockcount")) > 100)

    def wait_for_all_ln_rpc():
        lns = get_pods_with_label(lightning_selector)
        for v1_pod in lns:
            ln = v1_pod.metadata.name
            try:
                warnet(f"ln rpc {ln} getinfo")
            except Exception:
                log.info(f"LN node {ln} not ready for rpc yet")
                return False
        return True

    _wait_for_predicate(wait_for_all_ln_rpc)


def fund_wallets():
    """Fund each ln node with 10 regtest coins."""
    log.info("Funding wallets")
    outputs = ""
    lns = get_pods_with_label(lightning_selector)
    for v1_pod in lns:
        lnd = v1_pod.metadata.name
        addr = json.loads(warnet(f"ln rpc {lnd} newaddress p2wkh"))["address"]
        outputs += f',"{addr}":10'
    # trim first comma
    outputs = outputs[1:]
    log.info(warnet("bitcoin rpc tank-0000 sendmany '' '{" + outputs + "}'"))
    log.info(warnet("bitcoin rpc tank-0000 -generate 1"))


def everyone_has_a_host() -> bool:
    """Find out if each ln node has a host."""
    pods = get_pods_with_label(lightning_selector)
    host_havers = 0
    for pod in pods:
        name = pod.metadata.name
        result = warnet(f"ln host {name}")
        if len(result) > 1:
            host_havers += 1
    return host_havers == len(pods) and host_havers != 0


def wait_for_everyone_to_have_a_host():
    _wait_for_predicate(everyone_has_a_host)


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
        pods = get_pods_with_label(lightning_selector)
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

    for i in get_pods_with_label(lightning_selector):
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


def list_simln_podnames() -> list[str]:
    """Get a list of simln pod names"""
    return [pod.metadata.name for pod in get_pods_with_label("mission=simln")]


def download_results(pod_name: str):
    """Download SimLN results to the current directory"""
    download(pod_name, source_path=Path("/working/results"))
