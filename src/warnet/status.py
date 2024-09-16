import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .k8s import get_mission
from .network import _connected


@click.command()
def status():
    """Display the unified status of the Warnet network and active scenarios"""
    console = Console()

    tanks = _get_tank_status()
    scenarios = _get_deployed_scenarios()
    binaries = _get_active_binaries()

    # Create a unified table
    table = Table(title="Warnet Status", show_header=True, header_style="bold magenta")
    table.add_column("Component", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Status", style="yellow")

    # Add tanks to the table
    for tank in tanks:
        table.add_row("Tank", tank["name"], tank["status"])

    # Add a separator if there are both tanks and scenarios
    if tanks and scenarios:
        table.add_row("", "", "")

    # Add scenarios to the table
    active = 0
    if scenarios:
        for scenario in scenarios:
            table.add_row("Scenario", scenario["name"], scenario["status"])
            if scenario["status"] == "running" or scenario["status"] == "pending":
                active += 1
    else:
        table.add_row("Scenario", "No active scenarios", "")

    # Add a separator if there are both tanks or scenarios and binaries
    if (tanks or scenarios) and binaries:
        table.add_row("", "", "")

    # Add binaries to the table
    active_binaries = 0
    if binaries:
        for binary in binaries:
            table.add_row("Binary", binary["name"], binary["status"])
            if binary["status"] == "running" or binary["status"] == "pending":
                active_binaries += 1
    else:
        table.add_row("Binaries", "No active binaries", "")

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
    summary.append(f" | Active Binaries: {active_binaries}", style="bold red")
    console.print(summary)
    _connected(end="\r")


def _get_tank_status():
    tanks = get_mission("tank")
    return [{"name": tank.metadata.name, "status": tank.status.phase.lower()} for tank in tanks]


def _get_deployed_scenarios():
    commanders = get_mission("commander")
    return [{"name": c.metadata.name, "status": c.status.phase.lower()} for c in commanders]


def _get_active_binaries():
    binaries = get_mission("binary")
    return [{"name": b.metadata.name, "status": b.status.phase.lower()} for b in binaries]
