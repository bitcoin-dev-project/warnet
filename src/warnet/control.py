import base64
import json
import subprocess
import time
from pathlib import Path

import click
import inquirer
from inquirer.themes import GreenPassion
from rich import print
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

from .constants import COMMANDER_CHART
from .k8s import (
    delete_namespace,
    get_default_namespace,
    get_mission,
    get_pods,
)
from .process import run_command, stream_command

console = Console()


def get_active_scenarios():
    """Get list of active scenarios"""
    commanders = get_mission("commander")
    return [c.metadata.name for c in commanders]


@click.command()
@click.argument("scenario_name", required=False)
def stop(scenario_name):
    """Stop a running scenario or all scenarios"""
    active_scenarios = get_active_scenarios()

    if not active_scenarios:
        console.print("[bold red]No active scenarios found.[/bold red]")
        return

    if not scenario_name:
        table = Table(title="Active Scenarios", show_header=True, header_style="bold magenta")
        table.add_column("Number", style="cyan", justify="right")
        table.add_column("Scenario Name", style="green")

        for idx, name in enumerate(active_scenarios, 1):
            table.add_row(str(idx), name)

        console.print(table)

        choices = [str(i) for i in range(1, len(active_scenarios) + 1)] + ["a", "q"]
        choice = Prompt.ask(
            "[bold yellow]Enter the number of the scenario to stop, 'a' to stop all, or 'q' to quit[/bold yellow]",
            choices=choices,
            show_choices=False,
        )

        if choice == "q":
            console.print("[bold blue]Operation cancelled.[/bold blue]")
            return
        elif choice == "a":
            if Confirm.ask("[bold red]Are you sure you want to stop all scenarios?[/bold red]"):
                stop_all_scenarios(active_scenarios)
            else:
                console.print("[bold blue]Operation cancelled.[/bold blue]")
            return

        scenario_name = active_scenarios[int(choice) - 1]

    if scenario_name not in active_scenarios:
        console.print(f"[bold red]No active scenario found with name: {scenario_name}[/bold red]")
        return

    stop_scenario(scenario_name)


def stop_scenario(scenario_name):
    """Stop a single scenario"""
    cmd = f"kubectl delete pod {scenario_name}"
    if stream_command(cmd):
        console.print(f"[bold green]Successfully stopped scenario: {scenario_name}[/bold green]")
    else:
        console.print(f"[bold red]Failed to stop scenario: {scenario_name}[/bold red]")


def stop_all_scenarios(scenarios):
    """Stop all active scenarios"""
    with console.status("[bold yellow]Stopping all scenarios...[/bold yellow]"):
        for scenario in scenarios:
            stop_scenario(scenario)
    console.print("[bold green]All scenarios have been stopped.[/bold green]")


def list_active_scenarios():
    """List all active scenarios"""
    commanders = get_mission("commander")
    if not commanders:
        print("No active scenarios found.")
        return

    console = Console()
    table = Table(title="Active Scenarios", show_header=True, header_style="bold magenta")
    table.add_column("Name", style="cyan")
    table.add_column("Status", style="green")

    for commander in commanders:
        table.add_row(commander.metadata.name, commander.status.phase.lower())

    console.print(table)


@click.command()
def down():
    """Bring down a running warnet"""
    with console.status("[bold yellow]Bringing down the warnet...[/bold yellow]"):
        # Delete warnet-logging namespace
        if delete_namespace("warnet-logging"):
            console.print("[green]Warnet logging deleted[/green]")
        else:
            console.print("[red]Warnet logging NOT deleted[/red]")

    # Uninstall tanks
    tanks = get_mission("tank")
    with console.status("[yellow]Uninstalling tanks...[/yellow]"):
        for tank in tanks:
            cmd = f"helm uninstall {tank.metadata.name} --namespace {get_default_namespace()}"
            if stream_command(cmd):
                console.print(f"[green]Uninstalled tank: {tank.metadata.name}[/green]")
            else:
                console.print(f"[red]Failed to uninstall tank: {tank.metadata.name}[/red]")

    # Clean up scenarios and other pods
    pods = get_pods()
    with console.status("[yellow]Cleaning up remaining pods...[/yellow]"):
        for pod in pods.items:
            cmd = f"kubectl delete pod --ignore-not-found=true {pod.metadata.name} -n {get_default_namespace()}"
            if stream_command(cmd):
                console.print(f"[green]Deleted pod: {pod.metadata.name}[/green]")
            else:
                console.print(f"[red]Failed to delete pod: {pod.metadata.name}[/red]")

    console.print("[bold green]Warnet has been brought down.[/bold green]")


def get_active_network(namespace):
    """Get the name of the active network (Helm release) in the given namespace"""
    cmd = f"helm list --namespace {namespace} --output json"
    result = run_command(cmd)
    if result:
        import json

        releases = json.loads(result)
        if releases:
            # Assuming the first release is the active network
            return releases[0]["name"]
    return None


@click.command(context_settings={"ignore_unknown_options": True})
@click.argument("scenario_file", type=click.Path(exists=True, file_okay=True, dir_okay=False))
@click.argument("additional_args", nargs=-1, type=click.UNPROCESSED)
def run(scenario_file: str, additional_args: tuple[str]):
    """Run a scenario from a file"""
    scenario_path = Path(scenario_file).resolve()
    scenario_name = scenario_path.stem

    with open(scenario_path, "rb") as file:
        scenario_data = base64.b64encode(file.read()).decode()

    name = f"commander-{scenario_name.replace('_', '')}-{int(time.time())}"
    namespace = get_default_namespace()
    tankpods = get_mission("tank")
    tanks = [
        {
            "tank": tank.metadata.name,
            "chain": tank.metadata.labels["chain"],
            "rpc_host": tank.status.pod_ip,
            "rpc_port": int(tank.metadata.labels["RPCPort"]),
            "rpc_user": "user",
            "rpc_password": "password",
            "init_peers": [],
        }
        for tank in tankpods
    ]

    # Encode warnet data
    warnet_data = base64.b64encode(json.dumps(tanks).encode()).decode()

    try:
        # Construct Helm command
        helm_command = [
            "helm",
            "upgrade",
            "--install",
            "--namespace",
            namespace,
            "--set",
            f"fullnameOverride={name}",
            "--set",
            f"scenario={scenario_data}",
            "--set",
            f"warnet={warnet_data}",
        ]

        # Add additional arguments
        if additional_args:
            helm_command.extend(["--set", f"args={' '.join(additional_args)}"])

        helm_command.extend([name, COMMANDER_CHART])

        # Execute Helm command
        result = subprocess.run(helm_command, check=True, capture_output=True, text=True)

        if result.returncode == 0:
            print(f"Successfully started scenario: {scenario_name}")
            print(f"Commander pod name: {name}")
        else:
            print(f"Failed to start scenario: {scenario_name}")
            print(f"Error: {result.stderr}")

    except subprocess.CalledProcessError as e:
        print(f"Failed to start scenario: {scenario_name}")
        print(f"Error: {e.stderr}")


@click.command()
@click.argument("pod_name", type=str, default="")
@click.option("--follow", "-f", is_flag=True, default=False, help="Follow logs")
def logs(pod_name: str, follow: bool):
    """Show the logs of a pod"""
    follow_flag = "--follow" if follow else ""
    namespace = get_default_namespace()

    if pod_name:
        try:
            command = f"kubectl logs pod/{pod_name} -n {namespace} {follow_flag}"
            stream_command(command)
            return
        except Exception as e:
            print(f"Could not find the pod {pod_name}: {e}")

    try:
        pods = run_command(f"kubectl get pods -n {namespace} -o json")
        pods = json.loads(pods)
        pod_list = [item["metadata"]["name"] for item in pods["items"]]
    except Exception as e:
        print(f"Could not fetch any pods in namespace {namespace}: {e}")
        return

    if not pod_list:
        print(f"Could not fetch any pods in namespace {namespace}")
        return

    q = [
        inquirer.List(
            name="pod",
            message="Please choose a pod",
            choices=pod_list,
        )
    ]
    selected = inquirer.prompt(q, theme=GreenPassion())
    if selected:
        pod_name = selected["pod"]
        try:
            command = f"kubectl logs pod/{pod_name} -n {namespace} {follow_flag}"
            stream_command(command)
        except Exception as e:
            print(f"Please consider waiting for the pod to become available. Encountered: {e}")
    else:
        pass  # cancelled by user
