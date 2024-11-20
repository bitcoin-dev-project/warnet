import sys

import click
from kubernetes.config.config_exception import ConfigException
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from urllib3.exceptions import MaxRetryError

from .k8s import get_mission
from .network import _connected


@click.command()
def status():
    """Display the unified status of the Warnet network and active scenarios"""
    console = Console()

    try:
        tanks = _get_tank_status()
        scenarios = _get_deployed_scenarios()
    except ConfigException as e:
        print(e)
        print(
            "The kubeconfig file has not been properly set. This may mean that you need to "
            "authorize with a cluster such as by starting minikube, starting docker-desktop, or "
            "authorizing with a configuration file provided by a cluster administrator."
        )
        sys.exit(1)
    except MaxRetryError as e:
        print(e)
        print(
            "Warnet cannot get the status of a Warnet network. To resolve this, you may need to "
            "confirm you have access to a Warnet cluster. Start by checking your network "
            "connection. Then, if running a local cluster, check that minikube or docker-desktop "
            "is running properly. If you are trying to connect to a remote cluster, check that "
            "the relevant authorization file has been configured properly as instructed by a "
            "cluster administrator."
        )
        sys.exit(1)

    # Create a unified table
    table = Table(title="Warnet Status", show_header=True, header_style="bold magenta")
    table.add_column("Component", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Status", style="yellow")
    table.add_column("Namespace", style="green")

    # Add tanks to the table
    for tank in tanks:
        table.add_row("Tank", tank["name"], tank["status"], tank["namespace"])

    # Add a separator if there are both tanks and scenarios
    if tanks and scenarios:
        table.add_row("", "", "")

    # Add scenarios to the table
    active = 0
    if scenarios:
        for scenario in scenarios:
            table.add_row("Scenario", scenario["name"], scenario["status"], scenario["namespace"])
            if scenario["status"] == "running" or scenario["status"] == "pending":
                active += 1
    else:
        table.add_row("Scenario", "No active scenarios", "")

    # Create a panel to wrap the table
    panel = Panel(
        table,
        title="Warnet Overview",
        expand=False,
        border_style="blue",
        padding=(1, 1),
    )

    # Print the panel
    console.print(panel)

    # Print summary
    summary = Text()
    summary.append(f"\nTotal Tanks: {len(tanks)}", style="bold cyan")
    summary.append(f" | Active Scenarios: {active}", style="bold green")
    console.print(summary)
    _connected(end="\r")


def _get_tank_status():
    tanks = get_mission("tank")
    return [
        {
            "name": tank.metadata.name,
            "status": tank.status.phase.lower(),
            "namespace": tank.metadata.namespace,
        }
        for tank in tanks
    ]


def _get_deployed_scenarios():
    commanders = get_mission("commander")
    return [
        {
            "name": c.metadata.name,
            "status": c.status.phase.lower(),
            "namespace": c.metadata.namespace,
        }
        for c in commanders
    ]
