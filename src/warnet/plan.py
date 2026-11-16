import math
from pathlib import Path

import click
import yaml
from rich.console import Console
from rich.table import Table

from .constants import DEFAULTS_FILE, NETWORK_FILE

LN_IMPLS = ("lnd", "cln", "eclair", "ldk")

# Resource usage per pod: (CPU millicores, memory MiB).
# idle: measured with kubectl top on DigitalOcean (2026-11-14), nodes of a 300
#   node network after startup.
# busy: estimated typical use while ln_init opens channels and syncs gossip or
#   scenarios send payments. Not every pod is busy at the same time, so this is
#   less than the peak of a single pod. Refine with `warnet top --watch 15`.
PROFILES = {
    "bitcoind": {"idle": (5, 40), "busy": (50, 100)},
    "lnd": {"idle": (5, 55), "busy": (100, 200)},
    "cln": {"idle": (5, 30), "busy": (50, 100)},
    "eclair": {"idle": (12, 380), "busy": (200, 800)},
    "ldk": {"idle": (8, 10), "busy": (50, 50)},
    "commander": {"idle": (50, 200), "busy": (1000, 1024)},
    "service": {"idle": (10, 100), "busy": (100, 300)},
}

# Fraction of a node's CPU and memory Kubernetes lets pods use (DigitalOcean
# 32 vCPU / 64 GB nodes: 31.82 vCPU, 57.6 GiB)
ALLOCATABLE_CPU = 0.95
ALLOCATABLE_MEMORY = 0.88
# Spare pod slots, CPU and memory on top of what the network needs
HEADROOM = 0.1

# DigitalOcean Kubernetes node sizes: (slug, vCPU, memory GB)
DIGITALOCEAN_SIZES = {
    "CPU-Optimized (dedicated)": [
        ("c-2", 2, 4),
        ("c-4", 4, 8),
        ("c-8", 8, 16),
        ("c-16", 16, 32),
        ("c-32", 32, 64),
        ("c-48", 48, 96),
    ],
    "General Purpose (dedicated)": [
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
    "--nodes",
    type=click.IntRange(min=1),
    default=None,
    help="Number of Kubernetes nodes to size for (default: what the pods need)",
)
def plan(directory, max_pods, system_pods, nodes):
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
    busy_cpu = sum(n * PROFILES[kind]["busy"][0] for kind, n in pods.items()) / 1000
    busy_mem = sum(n * PROFILES[kind]["busy"][1] for kind, n in pods.items()) / 1024

    table = Table(title=f"Pods of {directory}")
    for column in ("Pod", "Count", "Idle CPU", "Idle memory", "Busy CPU", "Busy memory"):
        table.add_column(column, justify="left" if column == "Pod" else "right")
    for kind, n in sorted(pods.items(), key=lambda kv: -kv[1]):
        (icpu, imem), (bcpu, bmem) = PROFILES[kind]["idle"], PROFILES[kind]["busy"]
        table.add_row(
            kind,
            str(n),
            f"{n * icpu / 1000:.1f}",
            f"{n * imem / 1024:.1f} GiB",
            f"{n * bcpu / 1000:.1f}",
            f"{n * bmem / 1024:.1f} GiB",
        )
    table.add_section()
    table.add_row(
        "Total",
        str(total_pods),
        f"{idle_cpu:.1f}",
        f"{idle_mem:.1f} GiB",
        f"{busy_cpu:.1f}",
        f"{busy_mem:.1f} GiB",
        style="bold",
    )
    console.print(table)
    console.print(
        "CPU in cores. Idle was measured, busy (ln_init, payments) is an estimate: "
        "check with `warnet top --watch 15`.\n"
    )

    usable_pods = max_pods - system_pods
    if usable_pods <= 0:
        raise click.BadParameter("must be below --max-pods", param_hint="--system-pods")
    min_nodes = math.ceil(total_pods / usable_pods)
    recommended = math.ceil(total_pods * (1 + HEADROOM) / usable_pods)
    console.print(
        f"Pods: {total_pods} / ({max_pods} - {system_pods} system pods) per node = at least "
        f"{min_nodes} Kubernetes nodes, [bold green]{recommended} recommended[/] "
        f"({HEADROOM:.0%} headroom)"
    )
    count = nodes or recommended
    if count < min_nodes:
        console.print(f"[red]{count} nodes don't have pod slots for {total_pods} pods[/]")
    need_cpu = busy_cpu * (1 + HEADROOM) / count / ALLOCATABLE_CPU
    need_mem = busy_mem * (1 + HEADROOM) / count / ALLOCATABLE_MEMORY * 1024**3 / 1000**3
    console.print(
        f"Per node with {count} nodes: {need_cpu:.1f} vCPU and {need_mem:.1f} GB when busy\n"
    )

    sizes = Table(title=f"DigitalOcean node size for {count} nodes")
    for column in ("Node type", "Smallest size", "Cluster total"):
        sizes.add_column(column)
    for family, options in DIGITALOCEAN_SIZES.items():
        fit = next(((s, c, m) for s, c, m in options if c >= need_cpu and m >= need_mem), None)
        if fit:
            slug, cpu, mem = fit
            sizes.add_row(
                family, f"{slug} ({cpu} vCPU, {mem} GB)", f"{count * cpu} vCPU, {count * mem} GB"
            )
        else:
            sizes.add_row(family, "none big enough, add nodes", "")
    console.print(sizes)
    console.print(
        "Larger sizes only add unused capacity: DigitalOcean allows "
        f"{max_pods} pods per node whatever its size, so pod slots limit what fits on a node."
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
    has_channels = any(
        (node.get(impl) or {}).get("channels") for node, impl in zip(nodes, impls) if impl
    )
    # ln_init
    counts["commander"] = 1 if has_channels else 0
    counts["service"] = sum(
        1 for name in ("caddy", "fork_observer") if (network.get(name) or {}).get("enabled")
    )
    if (
        defaults.get("collectLogs")
        or defaults.get("metricsExport")
        or any(node.get("collectLogs") or node.get("metricsExport") for node in nodes)
    ):
        # loki, grafana and the prometheus stack (promtail runs on every node)
        counts["service"] += 8
    return {kind: n for kind, n in counts.items() if n}
