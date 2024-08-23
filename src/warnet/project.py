import os
import random

import click
import yaml


@click.group(name="project")
def project():
    """Manage a new warnet project"""


@project.command()
@click.option("--project_name", prompt="Enter the project name", type=str)
@click.option("--num_nodes", prompt="How many nodes?", type=int)
@click.option("--num_connections", prompt="How many connections should each node have?", type=int)
def new(project_name, num_nodes, num_connections):
    """
    Create a new project with a graph
    """

    # Create project directory
    os.makedirs(project_name, exist_ok=True)

    # Generate network.yaml
    nodes = []

    for i in range(num_nodes):
        node = {"name": f"tank-{i:04d}", "connect": []}

        # Add round-robin connection
        next_node = (i + 1) % num_nodes
        node["connect"].append(f"tank-{next_node:04d}")

        # Add random connections
        available_nodes = list(range(num_nodes))
        available_nodes.remove(i)
        if next_node in available_nodes:
            available_nodes.remove(next_node)

        for _ in range(min(num_connections - 1, len(available_nodes))):
            random_node = random.choice(available_nodes)
            node["connect"].append(f"tank-{random_node:04d}")
            available_nodes.remove(random_node)

        nodes.append(node)

    # Add image tag to the first node
    nodes[0]["image"] = {"tag": "v0.20.0"}

    network_yaml_data = {"nodes": nodes}

    with open(os.path.join(project_name, "network.yaml"), "w") as f:
        yaml.dump(network_yaml_data, f, default_flow_style=False)

    # Generate defaults.yaml
    defaults_yaml_content = """
chain: regtest

collectLogs: true
metricsExport: true

resources: {}
  # We usually recommend not to specify default resources and to leave this as a conscious
  # choice for the user. This also increases chances charts run on environments with little
  # resources, such as Minikube. If you do want to specify resources, uncomment the following
  # lines, adjust them as necessary, and remove the curly braces after 'resources:'.
  # limits:
  #   cpu: 100m
  #   memory: 128Mi
  # requests:
  #   cpu: 100m
  #   memory: 128Mi

image:
  repository: bitcoindevproject/bitcoin
  pullPolicy: IfNotPresent
  # Overrides the image tag whose default is the chart appVersion.
  tag: "27.0"

config: |
  dns=1
"""

    with open(os.path.join(project_name, "defaults.yaml"), "w") as f:
        f.write(defaults_yaml_content.strip())

    click.echo(
        f"Project '{project_name}' has been created with 'network.yaml' and 'defaults.yaml'."
    )
