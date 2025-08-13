import json
import os
import random
import sys
from pathlib import Path

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


@click.group(name="graph", hidden=True)
def graph():
    """Create and validate network graphs"""


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

            # Add round-robin connection
            next_node = (index + 1) % total_count
            node["addnode"].append(f"tank-{next_node:04d}")
            connections.add((index, next_node))

            # Add random connections
            available_nodes = list(range(total_count))
            available_nodes.remove(index)
            if next_node in available_nodes:
                available_nodes.remove(next_node)

            for _ in range(min(int(entry["connections"]) - 1, len(available_nodes))):
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

    # Start including channel open txs at this block height
    block = CHANNEL_OPEN_START_HEIGHT
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
