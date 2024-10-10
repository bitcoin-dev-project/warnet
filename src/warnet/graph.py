import os
import random
import sys
from importlib.resources import files
from pathlib import Path

import click
import inquirer
import yaml

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
    force_pull: bool,
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

    # Set pullPolicy
    if force_pull:
        defaults_yaml_content["image"]["pullPolicy"] = "Always"

    with open(os.path.join(datadir, "node-defaults.yaml"), "w") as f:
        yaml.dump(defaults_yaml_content, f, default_flow_style=False, sort_keys=False)

    click.echo(
        f"Project '{datadir}' has been created with 'network.yaml' and 'node-defaults.yaml'."
    )


def inquirer_create_network(project_path: Path):
    # Custom network configuration
    network_name = inquirer.text(
        message=click.style("Enter your network name", fg="blue", bold=True),
        validate=lambda _, x: len(x) > 0,
    )
    nodes = inquirer.list_input(
        message=click.style("How many nodes would you like?", fg="blue", bold=True),
        choices=["8", "12", "20", "50", "other"],
        default="12",
    )
    if nodes == "other":
        nodes = inquirer.text(
            message=click.style("Enter the number of nodes", fg="blue", bold=True),
            validate=lambda _, x: int(x) > 0,
        )
    connections = inquirer.list_input(
        message=click.style(
            "How many connections would you like each node to have?",
            fg="blue",
            bold=True,
        ),
        choices=["0", "1", "2", "8", "12", "other"],
        default="8",
    )
    if connections == "other":
        connections = inquirer.text(
            message=click.style("Enter the number of connections", fg="blue", bold=True),
            validate=lambda _, x: int(x) >= 0,
        )
    version = inquirer.list_input(
        message=click.style(
            "Which version would you like nodes to run by default?", fg="blue", bold=True
        ),
        choices=SUPPORTED_TAGS,
        default=DEFAULT_TAG,
    )
    force_pull = inquirer.confirm(
        message=click.style(
            "Would you like to force-pull bitcoin node images from dockerhub?", fg="blue", bold=True
        ),
        default=False,
    )

    # Inquire about fork observer
    fork_observer = inquirer.confirm(
        message=click.style(
            "Would you like to enable fork-observer on the network?", fg="blue", bold=True
        ),
        default=True,
    )
    fork_observer_query_interval = 20
    if fork_observer:
        fork_observer_query_interval = int(
            inquirer.text(
                message=click.style(
                    "How often would you like fork-observer to query node status (seconds)?",
                    fg="blue",
                    bold=True,
                ),
                validate=lambda _, x: int(x) > 0,
                default=fork_observer_query_interval,
            )
        )

    # Inquire about logging
    logging = inquirer.confirm(
        message=click.style(
            "Would you like to enable grafana logging on the network?", fg="blue", bold=True
        ),
        default=False,
    )

    caddy = fork_observer | logging
    custom_network_path = project_path / "networks" / network_name
    click.secho("\nGenerating custom network...", fg="yellow", bold=True)
    custom_graph(
        int(nodes),
        int(connections),
        version,
        custom_network_path,
        fork_observer,
        fork_observer_query_interval,
        caddy,
        logging,
        force_pull,
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
