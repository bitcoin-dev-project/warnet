import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .k8s import get_mission


@click.command()
def status():
    """Display the unified status of the Warnet network and active scenarios"""
    console = Console()

    tanks = _get_tank_status()
    scenarios = _get_active_scenarios()

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
    if scenarios:
        for scenario in scenarios:
            table.add_row("Scenario", scenario["name"], scenario["status"])
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
    summary.append(f" | Active Scenarios: {len(scenarios)}", style="bold green")
    console.print(summary)


def _get_tank_status():
    tanks = get_mission("tank")
    return [{"name": tank.metadata.name, "status": tank.status.phase.lower()} for tank in tanks]


def _get_active_scenarios():
    commanders = get_mission("commander")
    return [{"name": c.metadata.name, "status": c.status.phase.lower()} for c in commanders]
