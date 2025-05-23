import json
import os
import random
import sys
from importlib.resources import files
from pathlib import Path

import click
import inquirer
import yaml

from resources.scenarios.ln_framework.ln import Policy

from .constants import DEFAULT_TAG, SUPPORTED_TAGS


@click.group(name="graph", hidden=True)
def graph():
    """Create and validate network graphs"""


def custom_graph(
    num_nodes: int,
    num_connections: int,
    version: str,
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

    for i in range(num_nodes):
        node = {"name": f"tank-{i:04d}", "addnode": [], "image": {"tag": version}}

        # Add round-robin connection
        next_node = (i + 1) % num_nodes
        node["addnode"].append(f"tank-{next_node:04d}")
        connections.add((i, next_node))

        # Add random connections
        available_nodes = list(range(num_nodes))
        available_nodes.remove(i)
        if next_node in available_nodes:
            available_nodes.remove(next_node)

        for _ in range(min(num_connections - 1, len(available_nodes))):
            random_node = random.choice(available_nodes)
            # Avoid circular loops of A -> B -> A
            if (random_node, i) not in connections:
                node["addnode"].append(f"tank-{random_node:04d}")
                connections.add((i, random_node))
                available_nodes.remove(random_node)

        nodes.append(node)

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
    default_yaml_path = (
        files("resources.networks").joinpath("fork_observer").joinpath("node-defaults.yaml")
    )
    with open(str(default_yaml_path)) as f:
        defaults_yaml_content = yaml.safe_load(f)

    # Configure logging
    defaults_yaml_content["collectLogs"] = logging
    defaults_yaml_content["metricsExport"] = logging

    with open(os.path.join(datadir, "node-defaults.yaml"), "w") as f:
        yaml.dump(defaults_yaml_content, f, default_flow_style=False, sort_keys=False)

    click.echo(
        f"Project '{datadir}' has been created with 'network.yaml' and 'node-defaults.yaml'."
    )


def inquirer_create_network(project_path: Path):
    # Custom network configuration
    questions = [
        inquirer.Text(
            "network_name",
            message=click.style("Enter your network name", fg="blue", bold=True),
            validate=lambda _, x: len(x) > 0,
        ),
        inquirer.List(
            "nodes",
            message=click.style("How many nodes would you like?", fg="blue", bold=True),
            choices=["8", "12", "20", "50", "other"],
            default="12",
        ),
        inquirer.List(
            "connections",
            message=click.style(
                "How many connections would you like each node to have?",
                fg="blue",
                bold=True,
            ),
            choices=["0", "1", "2", "8", "12", "other"],
            default="8",
        ),
        inquirer.List(
            "version",
            message=click.style(
                "Which version would you like nodes to run by default?", fg="blue", bold=True
            ),
            choices=SUPPORTED_TAGS,
            default=DEFAULT_TAG,
        ),
    ]

    net_answers = inquirer.prompt(questions)
    if net_answers is None:
        click.secho("Setup cancelled by user.", fg="yellow")
        return False

    if net_answers["nodes"] == "other":
        custom_nodes = inquirer.prompt(
            [
                inquirer.Text(
                    "nodes",
                    message=click.style("Enter the number of nodes", fg="blue", bold=True),
                    validate=lambda _, x: int(x) > 0,
                )
            ]
        )
        if custom_nodes is None:
            click.secho("Setup cancelled by user.", fg="yellow")
            return False
        net_answers["nodes"] = custom_nodes["nodes"]

    if net_answers["connections"] == "other":
        custom_connections = inquirer.prompt(
            [
                inquirer.Text(
                    "connections",
                    message=click.style("Enter the number of connections", fg="blue", bold=True),
                    validate=lambda _, x: int(x) >= 0,
                )
            ]
        )
        if custom_connections is None:
            click.secho("Setup cancelled by user.", fg="yellow")
            return False
        net_answers["connections"] = custom_connections["connections"]
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
    custom_network_path = project_path / "networks" / net_answers["network_name"]
    click.secho("\nGenerating custom network...", fg="yellow", bold=True)
    custom_graph(
        int(net_answers["nodes"]),
        int(net_answers["connections"]),
        net_answers["version"],
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


@click.command()
@click.argument("graph_file_path", type=click.Path(exists=True, file_okay=True, dir_okay=False))
@click.argument("output_path", type=click.Path(exists=False, file_okay=False, dir_okay=True))
def import_network(graph_file_path: str, output_path: str):
    """Create a network from an imported lightning network graph JSON"""
    print(_import_network(graph_file_path, output_path))


def _import_network(graph_file_path, output_path):
    output_path = Path(output_path)
    graph_file_path = Path(graph_file_path).resolve()
    with open(graph_file_path) as graph_file:
        graph = json.loads(graph_file.read())

    tanks = {}
    pk_to_tank = {}
    tank_to_pk = {}
    index = 0
    for node in graph["nodes"]:
        tank = f"tank-{index:04d}"
        pk_to_tank[node["pub_key"]] = tank
        tank_to_pk[tank] = node["pub_key"]
        tanks[tank] = {"name": tank, "ln": {"lnd": True}, "lnd": {"channels": []}}
        index += 1
    print(f"Imported {index} nodes")

    sorted_edges = sorted(graph["edges"], key=lambda x: int(x["channel_id"]))

    # By default we start including channel open txs in block 300
    block = 300
    # Coinbase occupies the 0 position!
    index = 1
    count = 0
    for edge in sorted_edges:
        source = pk_to_tank[edge["node1_pub"]]
        channel = {
            "id": {"block": block, "index": index},
            "target": pk_to_tank[edge["node2_pub"]] + "-ln",
            "capacity": int(edge["capacity"]),
            "push_amt": int(edge["capacity"]) // 2,
            "source_policy": Policy.from_lnd_describegraph(edge["node1_policy"]).to_dict(),
            "target_policy": Policy.from_lnd_describegraph(edge["node2_policy"]).to_dict(),
        }
        tanks[source]["lnd"]["channels"].append(channel)
        index += 1
        if index > 1000:
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
