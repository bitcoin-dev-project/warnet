import heapq
import json
import os
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

import click
import inquirer
import yaml
from rich import print
from rich.console import Console
from rich.table import Table

from resources.scenarios.ln_framework.ln import (
    CHANNEL_OPEN_START_HEIGHT,
    CHANNEL_OPENS_PER_BLOCK,
    Policy,
)

from .constants import (
    DEFAULT_IMAGE_REPO,
    DEFAULT_TAG,
    FORK_OBSERVER_RPCAUTH,
    SUPPORTED_TAGS,
)


def custom_graph(
    tanks: list,
    datadir: Path,
    fork_observer: bool,
    fork_obs_query_interval: int,
    caddy: bool,
    logging: bool,
):
    try:
        datadir.mkdir(parents=False, exist_ok=False)
    except FileExistsError as e:
        print(e)
        print("Exiting network builder without overwriting")
        sys.exit(1)

    # Generate network.yaml
    nodes = []
    connections = set()
    total_count = sum(int(entry["count"]) for entry in tanks)
    index = 0

    for entry in tanks:
        for _ in range(int(entry["count"])):
            if ":" in entry["version"] and "/" in entry["version"]:
                repo, tag = entry["version"].split(":")
                image = {"repository": repo, "tag": tag}
            else:
                image = {"tag": entry["version"]}
            node = {"name": f"tank-{index:04d}", "addnode": [], "image": image}

            # Connect to other nodes
            available_nodes = list(range(total_count))
            # Do not connect to self
            available_nodes.remove(index)
            for count in range(min(int(entry["connections"]), len(available_nodes))):
                # Add neighbor connection first to create minimal round-robin
                if count == 0:
                    next_node = (index + 1) % total_count
                    node["addnode"].append(f"tank-{next_node:04d}")
                    connections.add((index, next_node))
                    if next_node in available_nodes:
                        available_nodes.remove(next_node)
                else:
                    random_node = random.choice(available_nodes)
                    # Avoid circular loops of A -> B -> A
                    if (random_node, index) not in connections:
                        node["addnode"].append(f"tank-{random_node:04d}")
                        connections.add((index, random_node))
                        available_nodes.remove(random_node)

            nodes.append(node)
            index += 1

    network_yaml_data = {"nodes": nodes}
    network_yaml_data["fork_observer"] = {
        "enabled": fork_observer,
        "configQueryInterval": fork_obs_query_interval,
    }
    network_yaml_data["caddy"] = {
        "enabled": caddy,
    }

    with open(os.path.join(datadir, "network.yaml"), "w") as f:
        yaml.dump(network_yaml_data, f, default_flow_style=False)

    # Generate node-defaults.yaml
    defaults_yaml_content = {
        "chain": "regtest",
        "image": {
            "repository": DEFAULT_IMAGE_REPO,
            "pullPolicy": "IfNotPresent",
        },
        "defaultConfig": f"rpcauth={FORK_OBSERVER_RPCAUTH}\n"
        + "rpcwhitelist=forkobserver:getchaintips,getblockheader,getblockhash,getblock,getnetworkinfo\n"
        + "rpcwhitelistdefault=0\n"
        + "debug=rpc\n",
    }

    # Configure logging
    defaults_yaml_content["collectLogs"] = logging
    defaults_yaml_content["metricsExport"] = logging

    with open(os.path.join(datadir, "node-defaults.yaml"), "w") as f:
        yaml.dump(defaults_yaml_content, f, default_flow_style=False, sort_keys=False)

    click.echo(
        f"Project '{datadir}' has been created with 'network.yaml' and 'node-defaults.yaml'."
    )


def inquirer_create_network(project_path: Path):
    network_name_prompt = inquirer.prompt(
        [
            inquirer.Text(
                "network_name",
                message=click.style("Enter your network name", fg="blue", bold=True),
                validate=lambda _, x: len(x) > 0,
            )
        ]
    )
    if not network_name_prompt:
        click.secho("Setup cancelled by user.", fg="yellow")
        return False

    tanks = []
    while True:
        table = Table(title="Current Network Population", show_header=True, header_style="magenta")
        table.add_column("Version", style="cyan")
        table.add_column("Count", style="green")
        table.add_column("Connections", style="green")

        for entry in tanks:
            table.add_row(entry["version"], entry["count"], entry["connections"])

        Console().print(table)

        add_more_prompt = inquirer.prompt(
            [
                inquirer.List(
                    "add_more",
                    message=click.style("How many nodes to add? (0 = done)", fg="blue", bold=True),
                    choices=["0", "4", "8", "12", "20", "50", "other"],
                    default="12",
                )
            ]
        )
        if not add_more_prompt:
            click.secho("Setup cancelled by user.", fg="yellow")
            return False
        if add_more_prompt["add_more"].startswith("0"):
            break

        if add_more_prompt["add_more"] == "other":
            how_many_prompt = inquirer.prompt(
                [
                    inquirer.Text(
                        "how_many",
                        message=click.style("Enter the number of nodes", fg="blue", bold=True),
                        validate=lambda _, x: int(x) > 0,
                    )
                ]
            )
            if not how_many_prompt:
                click.secho("Setup cancelled by user.", fg="yellow")
                return False
            how_many = how_many_prompt["how_many"]
        else:
            how_many = add_more_prompt["add_more"]

        tank_details_prompt = inquirer.prompt(
            [
                inquirer.List(
                    "version",
                    message=click.style(
                        "Which version would you like to add to network?", fg="blue", bold=True
                    ),
                    choices=["other"] + SUPPORTED_TAGS,
                    default=DEFAULT_TAG,
                ),
                inquirer.List(
                    "connections",
                    message=click.style(
                        "How many connections would you like each of these nodes to have?",
                        fg="blue",
                        bold=True,
                    ),
                    choices=["0", "1", "2", "8", "12", "other"],
                    default="8",
                ),
            ]
        )
        if not tank_details_prompt:
            click.secho("Setup cancelled by user.", fg="yellow")
            return False
            break
        if tank_details_prompt["version"] == "other":
            custom_version_prompt = inquirer.prompt(
                [
                    inquirer.Text(
                        "version",
                        message=click.style(
                            "Provide dockerhub repository/image:tag", fg="blue", bold=True
                        ),
                        validate=lambda _, x: "/" in x and ":" in x,
                    )
                ]
            )
            if not custom_version_prompt:
                click.secho("Setup cancelled by user.", fg="yellow")
                return False
            tank_details_prompt["version"] = custom_version_prompt["version"]

        if tank_details_prompt["connections"] == "other":
            how_many_conn_prompt = inquirer.prompt(
                [
                    inquirer.Text(
                        "how_many_conn",
                        message=click.style(
                            "Enter the number of connections", fg="blue", bold=True
                        ),
                        validate=lambda _, x: int(x) > 0,
                    )
                ]
            )
            if not how_many_conn_prompt:
                click.secho("Setup cancelled by user.", fg="yellow")
                return False
            how_many_conn = how_many_conn_prompt["how_many_conn"]
        else:
            how_many_conn = tank_details_prompt["connections"]

        tanks.append(
            {
                "version": tank_details_prompt["version"],
                "count": how_many,
                "connections": how_many_conn,
            }
        )

    fork_observer = click.prompt(
        click.style(
            "\nWould you like to enable fork-observer on the network?", fg="blue", bold=True
        ),
        type=bool,
        default=True,
    )
    fork_observer_query_interval = 20
    if fork_observer:
        fork_observer_query_interval = click.prompt(
            click.style(
                "\nHow often would you like fork-observer to query node status (seconds)?",
                fg="blue",
                bold=True,
            ),
            type=int,
            default=20,
        )

    logging = click.prompt(
        click.style(
            "\nWould you like to enable grafana logging on the network?", fg="blue", bold=True
        ),
        type=bool,
        default=False,
    )
    caddy = fork_observer | logging
    custom_network_path = project_path / "networks" / network_name_prompt["network_name"]
    click.secho("\nGenerating custom network...", fg="yellow", bold=True)
    custom_graph(
        tanks,
        custom_network_path,
        fork_observer,
        fork_observer_query_interval,
        caddy,
        logging,
    )
    return custom_network_path


@click.command()
def create():
    """Create a new warnet network"""
    try:
        project_path = Path(os.getcwd())
        # Check if the project has a networks directory
        if not (project_path / "networks").exists():
            click.secho(
                "The current directory does not have a 'networks' directory. Please run 'warnet init' or 'warnet new' first.",
                fg="red",
                bold=True,
            )
            return False
        custom_network_path = inquirer_create_network(project_path)
        click.secho("\nNew network created successfully!", fg="green", bold=True)
        click.echo("\nRun the following command to deploy this network:")
        click.echo(f"warnet deploy {custom_network_path}")
    except Exception as e:
        click.echo(f"{e}\n\n")
        click.secho(f"An error occurred while creating a new network:\n\n{e}\n\n", fg="red")
        click.secho(
            "Please report the above context to https://github.com/bitcoin-dev-project/warnet/issues",
            fg="yellow",
        )
        return False


LN_IMPLS = ["lnd", "cln", "eclair", "ldk"]

# The largest channel LND accepts, even with wumbo channels enabled
MAX_CHANNEL_CAPACITY = 1_000_000_000
# The smallest channel LND accepts, also the minimum warnet sets for eclair
MIN_CHANNEL_CAPACITY = 20_000
# ln_init funds each channel an eclair node opens with a UTXO big enough for
# its largest channel, because its Bitcoin Core wallet can't be told which UTXO
# to use. Don't make eclair nodes of nodes that would need more than this much
# on top of the capacity of their channels, e.g. hubs with one large channel.
ECLAIR_MAX_EXTRA_FUNDING = 1_000_000_000  # sats


@click.command()
@click.argument("graph_file_path", type=click.Path(exists=True, file_okay=True, dir_okay=False))
@click.argument("output_path", type=click.Path(exists=False, file_okay=False, dir_okay=True))
@click.option(
    "--ln-impls",
    default="lnd",
    show_default=True,
    help=f"Comma-separated lightning implementations to assign to nodes at random, from: {','.join(LN_IMPLS)}, or ALL for all of them",
)
@click.option("--seed", type=int, default=None, help="Random seed for assigning implementations")
@click.option(
    "--max-nodes",
    type=click.IntRange(min=2),
    default=None,
    help="Import a connected core of at most this many nodes, starting from the best connected node",
)
@click.option(
    "--max-channels",
    type=click.IntRange(min=1),
    default=None,
    help="With --max-nodes, import at most this many channels, keeping the network connected",
)
def import_network(
    graph_file_path: str,
    output_path: str,
    ln_impls: str,
    seed: Optional[int],
    max_nodes: Optional[int],
    max_channels: Optional[int],
):
    """Create a network from an imported lightning network graph JSON"""
    if ln_impls.strip() == "ALL":
        ln_impls = ",".join(LN_IMPLS)
    impls = [impl.strip() for impl in ln_impls.split(",") if impl.strip()]
    unknown = [impl for impl in impls if impl not in LN_IMPLS]
    if not impls or unknown:
        raise click.BadParameter(
            f"must be ALL or a comma-separated list of {', '.join(LN_IMPLS)}",
            param_hint="--ln-impls",
        )
    if max_channels is not None:
        if max_nodes is None:
            raise click.BadParameter("requires --max-nodes", param_hint="--max-channels")
        if max_channels < max_nodes - 1:
            raise click.BadParameter(
                f"must be at least --max-nodes - 1 ({max_nodes - 1}) to connect every node",
                param_hint="--max-channels",
            )
    print(_import_network(graph_file_path, output_path, impls, seed, max_nodes, max_channels))


def _usable_edges(graph):
    """Channels warnet can recreate: both policies known, capacity within ln_init's limits"""
    pub_keys = {node["pub_key"] for node in graph["nodes"]}
    edges = []
    dropped = 0
    clamped = 0
    for edge in graph["edges"]:
        if (
            not edge.get("node1_policy")
            or not edge.get("node2_policy")
            or edge["node1_pub"] not in pub_keys
            or edge["node2_pub"] not in pub_keys
        ):
            dropped += 1
            continue
        capacity = int(edge["capacity"])
        clamped_capacity = min(max(capacity, MIN_CHANNEL_CAPACITY), MAX_CHANNEL_CAPACITY)
        if clamped_capacity != capacity:
            clamped += 1
            edge = {**edge, "capacity": str(clamped_capacity)}
        edges.append(edge)
    if dropped:
        print(f"Dropped {dropped} channels without both policies")
    if clamped:
        print(
            f"Clamped the capacity of {clamped} channels to "
            f"{MIN_CHANNEL_CAPACITY}-{MAX_CHANNEL_CAPACITY} sats"
        )
    return edges


def _select_core(nodes, edges, max_nodes, max_channels):
    """
    Grow a connected core from the node with the most channels, always adding
    the node with the most channels to the nodes already selected. Ties are
    broken by channel count, total capacity and public key, so the result
    doesn't depend on the order of the input.
    Then keep the channel each node joined through, which connects them all,
    and fill up to max_channels with the largest remaining channels.
    """
    channels = defaultdict(list)
    degree = Counter()
    capacity = Counter()
    for edge in edges:
        for a, b in (
            (edge["node1_pub"], edge["node2_pub"]),
            (edge["node2_pub"], edge["node1_pub"]),
        ):
            channels[a].append((b, edge))
            degree[a] += 1
            capacity[a] += int(edge["capacity"])

    def rank(pk):
        return (degree[pk], capacity[pk], pk)

    start = max(channels, key=rank)
    selected = [start]
    selected_set = {start}
    links = Counter()
    # Best channel from each frontier node into the selected nodes
    best_link = {}
    heap = []

    def add(pk):
        for peer, edge in channels[pk]:
            if peer in selected_set:
                continue
            links[peer] += 1
            key = (int(edge["capacity"]), -int(edge["channel_id"]))
            if peer not in best_link or key > best_link[peer][0]:
                best_link[peer] = (key, edge)
            heapq.heappush(heap, (-links[peer], *(-x for x in rank(peer)[:2]), peer))

    add(start)
    tree = []
    while len(selected) < max_nodes and heap:
        neg_links, _, _, pk = heapq.heappop(heap)
        # Skip stale heap entries
        if pk in selected_set or -neg_links != links[pk]:
            continue
        selected.append(pk)
        selected_set.add(pk)
        tree.append(best_link[pk][1])
        add(pk)

    core_edges = [
        edge
        for edge in edges
        if edge["node1_pub"] in selected_set and edge["node2_pub"] in selected_set
    ]
    if max_channels is not None and len(core_edges) > max_channels:
        tree_ids = {edge["channel_id"] for edge in tree}
        extra = sorted(
            (edge for edge in core_edges if edge["channel_id"] not in tree_ids),
            key=lambda edge: (-int(edge["capacity"]), int(edge["channel_id"])),
        )
        core_edges = tree + extra[: max_channels - len(tree)]
    print(
        f"Selected a connected core of {len(selected)} of {len(channels)} nodes "
        f"with {len(core_edges)} channels"
    )
    selected_nodes = {node["pub_key"]: node for node in nodes}
    return [selected_nodes[pk] for pk in selected], core_edges


def _avoid_eclair_hubs(tank_to_impl, pk_to_tank, edges, impls, seed):
    """Assign another implementation to eclair nodes that would need too much funding"""
    others = [impl for impl in impls if impl != "eclair"]
    if "eclair" not in impls or not others:
        return
    # The first node of an edge opens the channel
    opened = defaultdict(list)
    for edge in edges:
        opened[pk_to_tank[edge["node1_pub"]]].append(int(edge["capacity"]))
    # A separate generator, so only these nodes change for a given seed
    rng = random.Random(f"{seed}-eclair")
    moved = []
    for tank, impl in tank_to_impl.items():
        capacities = opened.get(tank)
        if impl != "eclair" or not capacities:
            continue
        extra = len(capacities) * max(capacities) - sum(capacities)
        if extra > ECLAIR_MAX_EXTRA_FUNDING:
            tank_to_impl[tank] = rng.choice(others)
            moved.append(f"{tank} ({tank_to_impl[tank]})")
    if moved:
        print(
            f"Assigned other implementations to {len(moved)} nodes that would need more than "
            f"{ECLAIR_MAX_EXTRA_FUNDING // 100_000_000} BTC of extra funding as eclair nodes: "
            + ", ".join(moved)
        )


def _import_network(
    graph_file_path, output_path, impls=None, seed=None, max_nodes=None, max_channels=None
):
    output_path = Path(output_path)
    graph_file_path = Path(graph_file_path).resolve()
    with open(graph_file_path) as graph_file:
        graph = json.loads(graph_file.read())

    nodes = graph["nodes"]
    edges = _usable_edges(graph)
    if max_nodes is not None:
        nodes, edges = _select_core(nodes, edges, max_nodes, max_channels)

    impls = impls or ["lnd"]
    if len(impls) > 1:
        if seed is None:
            seed = random.randrange(2**32)
        print(f"Assigning lightning implementations {impls} at random with --seed {seed}")
    rng = random.Random(seed)

    pk_to_tank = {}
    tank_to_pk = {}
    tank_to_impl = {}
    index = 0
    for node in nodes:
        tank = f"tank-{index:04d}"
        pk_to_tank[node["pub_key"]] = tank
        tank_to_pk[tank] = node["pub_key"]
        tank_to_impl[tank] = rng.choice(impls)
        index += 1
    _avoid_eclair_hubs(tank_to_impl, pk_to_tank, edges, impls, seed)
    tanks = {
        tank: {"name": tank, "ln": {impl: True}, impl: {"channels": []}}
        for tank, impl in tank_to_impl.items()
    }
    print(f"Imported {index} nodes")
    if len(impls) > 1:
        for impl in impls:
            count = list(tank_to_impl.values()).count(impl)
            print(f"  {impl}: {count}")

    sorted_edges = sorted(edges, key=lambda x: int(x["channel_id"]))

    # Start including channel open txs at this block height
    block = CHANNEL_OPEN_START_HEIGHT
    # Coinbase occupies the 0 position!
    index = 1
    count = 0
    for edge in sorted_edges:
        source = pk_to_tank[edge["node1_pub"]]
        target = pk_to_tank[edge["node2_pub"]]
        channel = {
            "id": {"block": block, "index": index},
            "target": target + "-ln",
            "capacity": int(edge["capacity"]),
            "push_amt": int(edge["capacity"]) // 2,
        }
        # Only LND nodes can apply channel policies
        if tank_to_impl[source] == "lnd":
            channel["source_policy"] = Policy.from_lnd_describegraph(edge["node1_policy"]).to_dict()
        if tank_to_impl[target] == "lnd":
            channel["target_policy"] = Policy.from_lnd_describegraph(edge["node2_policy"]).to_dict()
        tanks[source][tank_to_impl[source]]["channels"].append(channel)
        index += 1
        if index > CHANNEL_OPENS_PER_BLOCK:
            index = 1
            block += 1
        count += 1

    print(f"Imported {count} channels")

    network = {"nodes": []}
    prev_node_name = list(tanks.keys())[-1]
    for name, obj in tanks.items():
        obj["name"] = name
        obj["addnode"] = [prev_node_name]
        prev_node_name = name
        network["nodes"].append(obj)

    output_path.mkdir(parents=True, exist_ok=True)
    # This file must exist and must contain at least one line of valid yaml
    with open(output_path / "node-defaults.yaml", "w") as f:
        f.write(f"imported_from: {graph_file_path}\n")
    # Here's the good stuff
    with open(output_path / "network.yaml", "w") as f:
        f.write(yaml.dump(network, sort_keys=False))
    return f"Network created in {output_path.resolve()}"
