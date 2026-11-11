import json
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from time import sleep, time

import click
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from kubernetes.utils import parse_quantity
from rich.console import Console
from rich.table import Table

from .constants import (
    COMMANDER_MISSION,
    INGRESS_NAMESPACE,
    KUBECONFIG,
    LIGHTNING_MISSION,
    LOCAL_CLUSTER_CONTEXTS,
    LOGGING_NAMESPACE,
    METRICS_API_SERVICE,
    METRICS_SERVER_HELM_COMMANDS,
    TANK_MISSION,
)
from .process import stream_command

# Seconds between the two samples network rates are computed from
NETWORK_SAMPLE_SECONDS = 5
# Seconds to wait for metrics-server to report its first metrics after installing it
METRICS_SERVER_TIMEOUT = 180

# Cluster wide usage (fraction of allocatable) above which the cluster is too small
HIGH_CPU = 0.8
HIGH_MEMORY = 0.85
HIGH_PODS = 0.9
HIGH_DISK = 0.85
# Usage of a single node above which the load is uneven
HOT_NODE = 0.9
# Cluster wide usage below which the cluster is larger than needed
LOW_CPU = 0.2
LOW_MEMORY = 0.3
LOW_PODS = 0.5

LN_IMPLS = ("lnd", "cln", "eclair", "ldk")


@click.command()
@click.option("--watch", "-w", type=float, help="Refresh every WATCH seconds")
@click.option(
    "--pods", "num_pods", default=10, show_default=True, help="Number of busiest pods to list"
)
@click.option("--yes", "-y", is_flag=True, help="Install metrics-server without asking if needed")
def top(watch, num_pods, yes):
    """Show cluster resource usage, to judge if the cluster fits the network and scenarios"""
    config.load_kube_config(config_file=KUBECONFIG)
    console = Console()
    if not metrics_available():
        console.print(
            "Cluster CPU and memory usage requires metrics-server, which is not installed.\n"
            "It is a small deployment in the kube-system namespace that keeps the latest "
            "usage of each node and pod in memory. Installing it requires cluster admin."
        )
        if yes or click.confirm("Install metrics-server into the cluster?", default=True):
            install_metrics_server(console)
        else:
            console.print("Showing what is available without metrics-server\n")

    try:
        previous = None
        while True:
            snapshot = collect()
            if previous is None and snapshot["summary"] and not watch:
                # Network rates need two samples
                sleep(NETWORK_SAMPLE_SECONDS)
                previous, snapshot = snapshot, collect()
            if watch:
                console.clear()
            render(console, snapshot, previous, num_pods)
            if not watch:
                return
            previous = snapshot
            sleep(watch)
    except KeyboardInterrupt:
        sys.exit(130)


def metrics_available() -> bool:
    try:
        service = client.ApiregistrationV1Api().read_api_service(METRICS_API_SERVICE)
    except ApiException as e:
        if e.status == 404:
            return False
        # Not allowed to read API services, try the metrics API itself
        return node_metrics() is not None
    conditions = service.status.conditions or []
    return any(c.type == "Available" and c.status == "True" for c in conditions)


def install_metrics_server(console):
    _, context = config.list_kube_config_contexts(config_file=KUBECONFIG)
    commands = list(METRICS_SERVER_HELM_COMMANDS)
    if context["name"].startswith(LOCAL_CLUSTER_CONTEXTS):
        commands[-1] += " --set 'args={--kubelet-insecure-tls}'"
    for command in commands:
        stream_command(command)
    console.print("Waiting for metrics-server to report the first metrics...")
    deadline = time() + METRICS_SERVER_TIMEOUT
    while time() < deadline:
        if metrics_available() and node_metrics():
            return
        sleep(5)
    console.print(
        f"[yellow]metrics-server didn't report metrics within {METRICS_SERVER_TIMEOUT} "
        "seconds, check `kubectl -n kube-system logs deploy/metrics-server`[/yellow]"
    )


def node_metrics():
    """{node: (CPU cores, memory bytes)} or None if metrics aren't available"""
    try:
        res = client.CustomObjectsApi().list_cluster_custom_object(
            "metrics.k8s.io", "v1beta1", "nodes"
        )
    except ApiException:
        return None
    return {
        item["metadata"]["name"]: (
            float(parse_quantity(item["usage"]["cpu"])),
            float(parse_quantity(item["usage"]["memory"])),
        )
        for item in res["items"]
    }


def pod_metrics():
    """{(namespace, pod): (CPU cores, memory bytes)} or None if metrics aren't available"""
    try:
        res = client.CustomObjectsApi().list_cluster_custom_object(
            "metrics.k8s.io", "v1beta1", "pods"
        )
    except ApiException:
        return None
    usage = {}
    for item in res["items"]:
        cpu = sum(float(parse_quantity(c["usage"]["cpu"])) for c in item["containers"])
        memory = sum(float(parse_quantity(c["usage"]["memory"])) for c in item["containers"])
        usage[(item["metadata"]["namespace"], item["metadata"]["name"])] = (cpu, memory)
    return usage


def kubelet_summary(node_name):
    """Disk and network stats from the node's kubelet, None if not allowed (nodes/proxy)"""
    try:
        res = client.CoreV1Api().connect_get_node_proxy_with_path(
            node_name, "stats/summary", _preload_content=False
        )
        return json.loads(res.data)["node"]
    except (ApiException, ValueError, KeyError):
        return None


def workload(pod) -> str:
    labels = pod.metadata.labels or {}
    mission = labels.get("mission")
    if mission == TANK_MISSION:
        return "bitcoind"
    if mission == LIGHTNING_MISSION:
        names = {c.name for c in pod.spec.containers}
        return next((impl for impl in LN_IMPLS if impl in names), "lightning")
    if mission == COMMANDER_MISSION:
        return "scenarios"
    namespace = pod.metadata.namespace
    if namespace == "kube-system":
        return "kubernetes"
    if namespace == LOGGING_NAMESPACE:
        return "logging"
    if namespace == INGRESS_NAMESPACE:
        return "ingress"
    return "other"


def requested(pod, resource) -> float:
    return sum(
        float(parse_quantity((c.resources.requests or {}).get(resource, "0")))
        for c in pod.spec.containers
        if c.resources
    )


def collect() -> dict:
    core = client.CoreV1Api()
    nodes = core.list_node().items
    pods = core.list_pod_for_all_namespaces().items
    used_by_node = node_metrics()
    used_by_pod = pod_metrics()
    with ThreadPoolExecutor(max_workers=16) as executor:
        summaries = dict(
            zip(
                [n.metadata.name for n in nodes],
                executor.map(kubelet_summary, [n.metadata.name for n in nodes]),
            )
        )

    node_stats = {}
    for node in nodes:
        name = node.metadata.name
        allocatable = node.status.allocatable
        conditions = {c.type: c.status for c in node.status.conditions or []}
        summary = summaries.get(name) or {}
        fs = summary.get("fs") or {}
        network = summary.get("network") or {}
        node_stats[name] = {
            "ready": conditions.get("Ready") == "True",
            "pressure": [
                t for t, s in conditions.items() if t.endswith("Pressure") and s == "True"
            ],
            "cpu": float(parse_quantity(allocatable["cpu"])),
            "memory": float(parse_quantity(allocatable["memory"])),
            "max_pods": int(allocatable["pods"]),
            "pods": 0,
            "cpu_requested": 0.0,
            "memory_requested": 0.0,
            "cpu_used": used_by_node[name][0] if used_by_node and name in used_by_node else None,
            "memory_used": used_by_node[name][1] if used_by_node and name in used_by_node else None,
            "disk_used": fs.get("usedBytes"),
            "disk": fs.get("capacityBytes"),
            "rx": network.get("rxBytes"),
            "tx": network.get("txBytes"),
        }

    unschedulable = Counter()
    starting = 0
    groups = defaultdict(lambda: {"pods": 0, "cpu": 0.0, "memory": 0.0})
    busiest = []
    for pod in pods:
        if pod.status.phase not in ("Pending", "Running"):
            continue
        key = (pod.metadata.namespace, pod.metadata.name)
        node_name = pod.spec.node_name
        if not node_name:
            reasons = [
                c.message or c.reason or "unknown"
                for c in pod.status.conditions or []
                if c.type == "PodScheduled" and c.status == "False"
            ]
            unschedulable[reasons[0] if reasons else "not scheduled yet"] += 1
            continue
        if pod.status.phase == "Pending":
            starting += 1
        if node_name in node_stats:
            stats = node_stats[node_name]
            stats["pods"] += 1
            stats["cpu_requested"] += requested(pod, "cpu")
            stats["memory_requested"] += requested(pod, "memory")
        group = groups[workload(pod)]
        group["pods"] += 1
        if used_by_pod and key in used_by_pod:
            cpu, memory = used_by_pod[key]
            group["cpu"] += cpu
            group["memory"] += memory
            busiest.append((f"{key[0]}/{key[1]}", workload(pod), node_name, cpu, memory))

    return {
        "time": time(),
        "nodes": node_stats,
        "unschedulable": unschedulable,
        "starting": starting,
        "groups": dict(groups),
        "busiest": sorted(busiest, key=lambda p: -p[3]),
        "metrics": used_by_node is not None,
        "summary": any(summaries.values()),
    }


def totals(snapshot) -> dict:
    nodes = snapshot["nodes"].values()

    def total(key):
        values = [n[key] for n in nodes if n[key] is not None]
        return sum(values) if values else None

    return {
        key: total(key)
        for key in (
            "cpu",
            "memory",
            "max_pods",
            "pods",
            "cpu_requested",
            "memory_requested",
            "cpu_used",
            "memory_used",
            "disk_used",
            "disk",
            "rx",
            "tx",
        )
    }


def ratio(part, whole):
    return part / whole if part is not None and whole else None


def assess(snapshot) -> tuple[str, list[str]]:
    """Verdict on the cluster size and the reasons for it"""
    t = totals(snapshot)
    nodes = snapshot["nodes"]
    under = []
    notes = []
    for reason, count in snapshot["unschedulable"].most_common():
        under.append(f"{count} pods can't be scheduled: {reason}")
    for name, n in nodes.items():
        if not n["ready"]:
            under.append(f"node {name} is not ready")
        for pressure in n["pressure"]:
            under.append(f"node {name} reports {pressure}")
    checks = [
        ("CPU", ratio(t["cpu_used"], t["cpu"]), HIGH_CPU),
        ("memory", ratio(t["memory_used"], t["memory"]), HIGH_MEMORY),
        ("pod slots", ratio(t["pods"], t["max_pods"]), HIGH_PODS),
        ("disk", ratio(t["disk_used"], t["disk"]), HIGH_DISK),
    ]
    for resource, used, high in checks:
        if used is not None and used > high:
            under.append(f"cluster {resource} usage is {used:.0%}")
    requests = ratio(t["cpu_requested"], t["cpu"])
    if requests is not None and requests > HIGH_CPU:
        notes.append(f"{requests:.0%} of the cluster's CPU is requested, new pods may not fit")
    hot = [
        name
        for name, n in nodes.items()
        if (ratio(n["cpu_used"], n["cpu"]) or 0) > HOT_NODE
        or (ratio(n["memory_used"], n["memory"]) or 0) > HOT_NODE
    ]
    if hot and len(hot) < len(nodes):
        notes.append(f"uneven load, over {HOT_NODE:.0%} CPU or memory on: {', '.join(hot)}")
    if snapshot["starting"]:
        notes.append(f"{snapshot['starting']} pods are still starting")
    if not snapshot["metrics"]:
        notes.append("CPU and memory usage unknown without metrics-server")

    if under:
        return "UNDER-PROVISIONED", under + notes
    cpu = ratio(t["cpu_used"], t["cpu"])
    memory = ratio(t["memory_used"], t["memory"])
    pods = ratio(t["pods"], t["max_pods"])
    if (
        cpu is not None
        and memory is not None
        and cpu < LOW_CPU
        and memory < LOW_MEMORY
        and pods < LOW_PODS
    ):
        return "OVER-PROVISIONED", [
            f"only {cpu:.0%} CPU, {memory:.0%} memory and {pods:.0%} of pod slots used. "
            "Fewer or smaller nodes would do, if the network and scenarios are running"
        ] + notes
    if not snapshot["metrics"]:
        return "UNKNOWN", notes
    return "SUFFICIENT", notes


def cores(value):
    return "-" if value is None else f"{value:.1f}"


def gib(value):
    return "-" if value is None else f"{value / 2**30:.1f}"


def percent(part, whole):
    value = ratio(part, whole)
    return "" if value is None else f" ({value:.0%})"


def usage(used, whole, fmt):
    if used is None:
        return f"- / {fmt(whole)}"
    return f"{fmt(used)} / {fmt(whole)}{percent(used, whole)}"


def rate(current, previous, seconds):
    if current is None or previous is None or seconds <= 0:
        return "-"
    return f"{max(current - previous, 0) / seconds / 2**20:.1f}"


def render(console, snapshot, previous, num_pods):
    seconds = snapshot["time"] - previous["time"] if previous else 0
    table = Table(title="Cluster nodes")
    table.add_column("Node", no_wrap=True)
    for column in (
        "CPU cores used",
        "CPU requested",
        "Memory GiB used",
        "Memory requested",
        "Pods",
    ):
        table.add_column(column, justify="right")
    # Only with access to the kubelet stats
    if snapshot["summary"]:
        table.add_column("Disk GiB used", justify="right")
        table.add_column("Net MiB/s rx / tx", justify="right")
    table.add_column("Status")

    def row(name, n, prev, status):
        cells = [
            name,
            usage(n["cpu_used"], n["cpu"], cores),
            f"{cores(n['cpu_requested'])}{percent(n['cpu_requested'], n['cpu'])}",
            usage(n["memory_used"], n["memory"], gib),
            f"{gib(n['memory_requested'])}{percent(n['memory_requested'], n['memory'])}",
            f"{n['pods']} / {n['max_pods']}{percent(n['pods'], n['max_pods'])}",
        ]
        if snapshot["summary"]:
            rx = rate(n["rx"], prev["rx"] if prev else None, seconds)
            tx = rate(n["tx"], prev["tx"] if prev else None, seconds)
            cells += [usage(n["disk_used"], n["disk"], gib) if n["disk"] else "-", f"{rx} / {tx}"]
        return (*cells, status)

    for name, n in sorted(snapshot["nodes"].items()):
        prev = previous["nodes"].get(name) if previous else None
        status = ", ".join(([] if n["ready"] else ["NotReady"]) + n["pressure"]) or "ok"
        table.add_row(*row(name, n, prev, status))
    total = totals(snapshot)
    table.add_section()
    table.add_row(
        *row(
            f"Total ({len(snapshot['nodes'])} node{'s' if len(snapshot['nodes']) != 1 else ''})",
            total,
            totals(previous) if previous else None,
            "",
        ),
        style="bold",
    )
    console.print(table)

    if snapshot["groups"]:
        groups = Table(title="Usage by workload")
        for column in (
            "Workload",
            "Pods",
            "CPU cores",
            "CPU per pod",
            "Memory GiB",
            "Memory per pod",
        ):
            groups.add_column(column, justify="left" if column == "Workload" else "right")
        for name, g in sorted(snapshot["groups"].items(), key=lambda kv: -kv[1]["cpu"]):
            known = snapshot["metrics"]
            groups.add_row(
                name,
                str(g["pods"]),
                cores(g["cpu"]) if known else "-",
                f"{g['cpu'] / g['pods']:.2f}" if known else "-",
                gib(g["memory"]) if known else "-",
                f"{g['memory'] / g['pods'] / 2**20:.0f} MiB" if known else "-",
            )
        console.print(groups)

    if snapshot["busiest"] and num_pods:
        pods = Table(title=f"Busiest {num_pods} pods by CPU")
        for column in ("Pod", "Workload", "Node", "CPU cores", "Memory MiB"):
            pods.add_column(
                column, justify="right" if column.startswith(("CPU", "Mem")) else "left"
            )
        for name, group, node, cpu, memory in snapshot["busiest"][:num_pods]:
            pods.add_row(name, group, node, f"{cpu:.2f}", f"{memory / 2**20:.0f}")
        console.print(pods)

    verdict, reasons = assess(snapshot)
    color = {"UNDER-PROVISIONED": "red", "OVER-PROVISIONED": "yellow", "SUFFICIENT": "green"}
    console.print(f"[bold {color.get(verdict, 'white')}]Cluster is {verdict}[/]")
    for reason in reasons:
        console.print(f"  - {reason}")
    if not snapshot["summary"]:
        console.print(
            "  Disk and network usage need access to the kubelet stats (nodes/proxy permission)"
        )
