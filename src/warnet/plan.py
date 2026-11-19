import math
from pathlib import Path

import click
import yaml
from rich.console import Console
from rich.table import Table

from .constants import DEFAULTS_FILE, NETWORK_FILE
from .deploy import init_scenarios, logging_required

LN_IMPLS = ("lnd", "cln", "eclair", "ldk")

# Resource usage per pod.
# idle: (CPU millicores, memory MiB) measured with kubectl top on DigitalOcean
#   (2026-11-14), nodes of a 300 node network after startup.
# startup: CPU millicores while warnet deploy starts every pod at once, which
#   is when a cluster needs the most CPU. Estimated from two DigitalOcean
#   clusters: a 300 node network (estimated 393 cores) on 10 x 8 vCPU nodes
#   overloaded them (load 80-195 per node, bitcoind took 4 minutes to start, LN
#   nodes crash looped), a 100 node network (estimated 124 cores) on 10 x 32 vCPU
#   nodes started cleanly.
# memory: MiB once the network is running, ln_init and payments included.
PROFILES = {
    "bitcoind": {"idle": (5, 40), "startup": 500, "memory": 100},
    "lnd": {"idle": (5, 55), "startup": 1000, "memory": 200},
    "cln": {"idle": (5, 30), "startup": 500, "memory": 100},
    "eclair": {"idle": (12, 380), "startup": 2000, "memory": 800},
    "ldk": {"idle": (8, 10), "startup": 300, "memory": 50},
    "commander": {"idle": (50, 200), "startup": 1000, "memory": 1024},
    "service": {"idle": (10, 100), "startup": 300, "memory": 300},
}
# How many times its vCPUs a cluster can be asked for at startup: pods take
# longer to start but well within their startup probes. A guess between the
# two clusters above (0.4 started cleanly, 4.9 failed).
STARTUP_OVERSUBSCRIPTION = 2

# Fraction of a node's CPU and memory Kubernetes lets pods use (DigitalOcean
# 32 vCPU / 64 GB nodes: 31.82 vCPU, 57.6 GiB)
ALLOCATABLE_CPU = 0.95
ALLOCATABLE_MEMORY = 0.88
# Spare pod slots, CPU and memory on top of what the network needs
HEADROOM = 0.1

# DigitalOcean Kubernetes node sizes: (slug, vCPU, memory GB)
DIGITALOCEAN_SIZES = {
    "CPU-Optimized": [
        ("c-2", 2, 4),
        ("c-4", 4, 8),
        ("c-8", 8, 16),
        ("c-16", 16, 32),
        ("c-32", 32, 64),
        ("c-48", 48, 96),
    ],
    "General Purpose": [
        ("g-2vcpu-8gb", 2, 8),
        ("g-4vcpu-16gb", 4, 16),
        ("g-8vcpu-32gb", 8, 32),
        ("g-16vcpu-64gb", 16, 64),
        ("g-32vcpu-128gb", 32, 128),
        ("g-48vcpu-192gb", 48, 192),
    ],
    "Basic (shared CPU)": [
        ("s-2vcpu-4gb", 2, 4),
        ("s-4vcpu-8gb", 4, 8),
        ("s-8vcpu-16gb", 8, 16),
    ],
}


@click.command()
@click.argument("directory", type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option(
    "--max-pods",
    default=110,
    show_default=True,
    help="Maximum pods per Kubernetes node (110 on DigitalOcean)",
)
@click.option(
    "--system-pods",
    default=25,
    show_default=True,
    help="Pods per Kubernetes node used by the cluster itself (networking, DNS, ...)",
)
@click.option(
    "--max-nodes",
    type=click.IntRange(min=1),
    default=100,
    show_default=True,
    help="Largest cluster to consider, in Kubernetes nodes",
)
def plan(directory, max_pods, system_pods, max_nodes):
    """Estimate the Kubernetes cluster (node count and size) a network needs"""
    directory = Path(directory)
    with open(directory / NETWORK_FILE) as f:
        network = yaml.load(f, Loader=getattr(yaml, "CSafeLoader", yaml.SafeLoader)) or {}
    with open(directory / DEFAULTS_FILE) as f:
        defaults = yaml.safe_load(f) or {}
    console = Console()

    pods = count_pods(network, defaults)
    total_pods = sum(pods.values())
    idle_cpu = sum(n * PROFILES[kind]["idle"][0] for kind, n in pods.items()) / 1000
    idle_mem = sum(n * PROFILES[kind]["idle"][1] for kind, n in pods.items()) / 1024
    startup_cpu = sum(n * PROFILES[kind]["startup"] for kind, n in pods.items()) / 1000
    memory = sum(n * PROFILES[kind]["memory"] for kind, n in pods.items()) / 1024

    table = Table(title=f"Pods of {directory}")
    for column in ("Pod", "Count", "Idle CPU", "Idle memory", "Startup CPU", "Memory"):
        table.add_column(column, justify="left" if column == "Pod" else "right")
    for kind, n in sorted(pods.items(), key=lambda kv: -kv[1]):
        profile = PROFILES[kind]
        table.add_row(
            kind,
            str(n),
            f"{n * profile['idle'][0] / 1000:.1f}",
            f"{n * profile['idle'][1] / 1024:.1f} GiB",
            f"{n * profile['startup'] / 1000:.0f}",
            f"{n * profile['memory'] / 1024:.1f} GiB",
        )
    table.add_section()
    table.add_row(
        "Total",
        str(total_pods),
        f"{idle_cpu:.1f}",
        f"{idle_mem:.1f} GiB",
        f"{startup_cpu:.0f}",
        f"{memory:.1f} GiB",
        style="bold",
    )
    console.print(table)
    console.print(
        "CPU in cores. Idle was measured. Startup CPU (every pod starting at once, the "
        "most a deploy needs) and memory are estimates.\n"
    )

    usable_pods = max_pods - system_pods
    if usable_pods <= 0:
        raise click.BadParameter("must be below --max-pods", param_hint="--system-pods")
    pod_nodes = math.ceil(total_pods * (1 + HEADROOM) / usable_pods)
    need_vcpu = startup_cpu / STARTUP_OVERSUBSCRIPTION / ALLOCATABLE_CPU
    need_gb = memory * (1 + HEADROOM) / ALLOCATABLE_MEMORY * 1024**3 / 1000**3
    console.print(
        f"The cluster needs at least [bold]{pod_nodes} nodes[/] for {total_pods} pods "
        f"({max_pods} per node, {system_pods} for the system, {HEADROOM:.0%} spare), "
        f"[bold]{need_vcpu:.0f} vCPU[/] to start them (startup CPU / "
        f"{STARTUP_OVERSUBSCRIPTION}) and [bold]{need_gb:.0f} GB[/] of memory\n"
    )

    sizes = Table(title="DigitalOcean clusters that fit")
    for column in ("Type", "Node size", "Nodes", "Cluster total", "Limited by"):
        sizes.add_column(column, justify="right" if column == "Nodes" else "left")
    options = []
    for family, family_sizes in DIGITALOCEAN_SIZES.items():
        for slug, vcpu, gb in family_sizes:
            limits = {
                "pod slots": pod_nodes,
                "CPU": math.ceil(need_vcpu / vcpu),
                "memory": math.ceil(need_gb / gb),
            }
            count = max(limits.values())
            if count > max_nodes:
                continue
            binding = max(limits, key=limits.get)
            options.append((family, slug, vcpu, gb, count, binding))
    for family, slug, vcpu, gb, count, binding in options:
        sizes.add_row(
            family,
            f"{slug} ({vcpu} vCPU, {gb} GB)",
            str(count),
            f"{count * vcpu} vCPU, {count * gb} GB",
            binding,
        )
    console.print(sizes)
    console.print(
        "Sizes limited by pod slots have CPU or memory to spare, a smaller size of the same "
        "type would need more nodes. Shared CPU (Basic) nodes may be slower at startup."
    )


def node_impl(node, defaults):
    """The LN implementation of a network node, None without LN"""
    ln = {**(defaults.get("ln") or {}), **(node.get("ln") or {})}
    return next((impl for impl in LN_IMPLS if ln.get(impl)), None)


def count_pods(network, defaults) -> dict:
    """{kind: count} of the pods warnet deploy creates"""
    nodes = network.get("nodes") or []
    counts = {"bitcoind": len(nodes)}
    impls = [node_impl(node, defaults) for node in nodes]
    for impl in LN_IMPLS:
        counts[impl] = impls.count(impl)
    # addconnection_init and ln_init, which run one after the other
    needs_ln_init, addconnections = init_scenarios(network, defaults)
    counts["commander"] = 1 if needs_ln_init or addconnections else 0
    counts["service"] = sum(
        1 for name in ("caddy", "fork_observer") if (network.get(name) or {}).get("enabled")
    )
    if logging_required(network, defaults):
        # loki, grafana and the prometheus stack (promtail runs on every node)
        counts["service"] += 8
    return {kind: n for kind, n in counts.items() if n}
