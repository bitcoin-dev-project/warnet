import base64
import json
import os
import shlex
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import click
import inquirer
from inquirer.themes import GreenPassion
from rich import print
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

from .constants import BINARY_CHART, COMMANDER_CHART, LOGGING_NAMESPACE
from .deploy import _port_stop_internal
from .k8s import (
    get_default_namespace,
    get_mission,
    get_pods,
    snapshot_bitcoin_datadir,
)
from .process import run_command, stream_command

console = Console()


@click.command()
@click.argument("scenario_name", required=False)
def stop(scenario_name):
    """Stop a running scenario or all scenarios"""
    active_scenarios = [sc.metadata.name for sc in get_mission("commander")]

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
    """Stop a single scenario using Helm"""
    # Stop the pod immediately (faster than uninstalling)
    namespace = get_default_namespace()
    cmd = f"kubectl --namespace {namespace} delete pod {scenario_name} --grace-period=0 --force"
    if stream_command(cmd):
        console.print(f"[bold green]Successfully stopped scenario: {scenario_name}[/bold green]")
    else:
        console.print(f"[bold red]Failed to stop scenario: {scenario_name}[/bold red]")

    # Then uninstall via helm (non-blocking)
    command = f"helm uninstall {scenario_name} --namespace {namespace} --wait=false"

    # Run the helm uninstall command in the background
    subprocess.Popen(command, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    console.print(
        f"[bold yellow]Initiated helm uninstall for release: {scenario_name}[/bold yellow]"
    )


def stop_all_scenarios(scenarios):
    """Stop all active scenarios using Helm"""
    with console.status("[bold yellow]Stopping all scenarios...[/bold yellow]"):
        for scenario in scenarios:
            stop_scenario(scenario)
    console.print("[bold green]All scenarios have been stopped.[/bold green]")


@click.command()
def down():
    """Bring down a running warnet quickly"""
    console.print("[bold yellow]Bringing down the warnet...[/bold yellow]")

    namespaces = [get_default_namespace(), LOGGING_NAMESPACE]

    def uninstall_release(namespace, release_name):
        cmd = f"helm uninstall {release_name} --namespace {namespace} --wait=false"
        subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Initiated uninstall for: {release_name} in namespace {namespace}"

    def delete_pod(pod_name, namespace):
        cmd = f"kubectl delete pod --ignore-not-found=true {pod_name} -n {namespace} --grace-period=0 --force"
        subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Initiated deletion of pod: {pod_name} in namespace {namespace}"

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []

        # Uninstall Helm releases
        for namespace in namespaces:
            command = f"helm list --namespace {namespace} -o json"
            result = run_command(command)
            if result:
                releases = json.loads(result)
                for release in releases:
                    futures.append(executor.submit(uninstall_release, namespace, release["name"]))

        # Delete remaining pods
        pods = get_pods()
        for pod in pods.items:
            futures.append(executor.submit(delete_pod, pod.metadata.name, pod.metadata.namespace))

        # Wait for all tasks to complete and print results
        for future in as_completed(futures):
            console.print(f"[yellow]{future.result()}[/yellow]")

    # Shutdown any port forwarding
    _port_stop_internal("caddy", namespaces[1])
    console.print("[bold yellow]Teardown process initiated for all components.[/bold yellow]")
    console.print("[bold yellow]Note: Some processes may continue in the background.[/bold yellow]")
    console.print("[bold green]Warnet teardown process completed.[/bold green]")


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
    """
    Run a scenario from a file.
    Pass `-- --help` to get individual scenario help
    """
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
            if "--help" in additional_args or "-h" in additional_args:
                return subprocess.run([sys.executable, scenario_path, "--help"])

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


@click.command(context_settings={"ignore_unknown_options": True})
@click.argument("file", type=click.Path(exists=True, file_okay=True, dir_okay=False))
@click.argument("additional_args", nargs=-1, type=click.UNPROCESSED)
def run_binary(file: str, additional_args: tuple[str]):
    """
    Run a file in warnet
    Pass `-- --help` to get individual scenario help
    """
    file_path = Path(file).resolve()
    file_name = file_path.stem

    name = f"binary-{file_name.replace('_', '')}-{int(time.time())}"
    namespace = get_default_namespace()

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
            f"pod.name={name}",
        ]

        # Add additional arguments
        if additional_args:
            helm_command.extend(["--set", f"args={' '.join(additional_args)}"])
            if "--help" in additional_args or "-h" in additional_args:
                return subprocess.run([sys.executable, file_path, "--help"])

        helm_command.extend([name, BINARY_CHART])

        # Execute Helm command to start the pod
        result = subprocess.run(helm_command, check=True, capture_output=True, text=True)

        # Wait for the pod to be ready
        wait_command = [
            "kubectl",
            "wait",
            "--for=condition=PodReadyToStartContainers",
            "pod",
            "--namespace",
            namespace,
            "--timeout=30s",
            name,
        ]
        subprocess.run(wait_command, check=True)

        # Copy the binary into the container using k8s
        command = f"kubectl cp {file_path} -n {namespace} {name}:/data/binary -c {name}-runner"
        subprocess.run(shlex.split(command))

        if result.returncode == 0:
            print(f"Successfully started binary: {file_name}")
            print(f"Pod name: {name}")
        else:
            print(f"Failed to start binary: {file_name}")
            print(f"Error: {result.stderr}")

    except subprocess.CalledProcessError as e:
        print(f"Failed to start binary: {file_name}")
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


@click.command()
@click.argument("tank_name", required=False)
@click.option("--all", "-a", "snapshot_all", is_flag=True, help="Snapshot all running tanks")
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default="./warnet-snapshots",
    help="Output directory for snapshots",
)
@click.option(
    "--filter",
    "-f",
    type=str,
    help="Comma-separated list of directories and/or files to include in the snapshot",
)
def snapshot(tank_name, snapshot_all, output, filter):
    """Create a snapshot of a tank's Bitcoin data or snapshot all tanks"""
    tanks = get_mission("tank")

    if not tanks:
        console.print("[bold red]No active tanks found.[/bold red]")
        return

    # Create the output directory if it doesn't exist
    os.makedirs(output, exist_ok=True)

    filter_list = [f.strip() for f in filter.split(",")] if filter else None
    if snapshot_all:
        snapshot_all_tanks(tanks, output, filter_list)
    elif tank_name:
        snapshot_single_tank(tank_name, tanks, output, filter_list)
    else:
        select_and_snapshot_tank(tanks, output, filter_list)


def find_tank_by_name(tanks, tank_name):
    for tank in tanks:
        if tank.metadata.name == tank_name:
            return tank
    return None


def snapshot_all_tanks(tanks, output_dir, filter_list):
    with console.status("[bold yellow]Snapshotting all tanks...[/bold yellow]"):
        for tank in tanks:
            tank_name = tank.metadata.name
            chain = tank.metadata.labels["chain"]
            snapshot_tank(tank_name, chain, output_dir, filter_list)
    console.print("[bold green]All tank snapshots completed.[/bold green]")


def snapshot_single_tank(tank_name, tanks, output_dir, filter_list):
    tank = find_tank_by_name(tanks, tank_name)
    if tank:
        chain = tank.metadata.labels["chain"]
        snapshot_tank(tank_name, chain, output_dir, filter_list)
    else:
        console.print(f"[bold red]No active tank found with name: {tank_name}[/bold red]")


def select_and_snapshot_tank(tanks, output_dir, filter_list):
    table = Table(title="Active Tanks", show_header=True, header_style="bold magenta")
    table.add_column("Number", style="cyan", justify="right")
    table.add_column("Tank Name", style="green")

    for idx, tank in enumerate(tanks, 1):
        table.add_row(str(idx), tank.metadata.name)

    console.print(table)

    choices = [str(i) for i in range(1, len(tanks) + 1)] + ["q"]
    choice = Prompt.ask(
        "[bold yellow]Enter the number of the tank to snapshot, or 'q' to quit[/bold yellow]",
        choices=choices,
        show_choices=False,
    )

    if choice == "q":
        console.print("[bold blue]Operation cancelled.[/bold blue]")
        return

    selected_tank = tanks[int(choice) - 1]
    tank_name = selected_tank.metadata.name
    chain = selected_tank.metadata.labels["chain"]
    snapshot_tank(tank_name, chain, output_dir, filter_list)


def snapshot_tank(tank_name, chain, output_dir, filter_list):
    try:
        output_path = Path(output_dir).resolve()
        snapshot_bitcoin_datadir(tank_name, chain, str(output_path), filter_list)
        console.print(
            f"[bold green]Successfully created snapshot for tank: {tank_name}[/bold green]"
        )
    except Exception as e:
        console.print(
            f"[bold red]Failed to create snapshot for tank {tank_name}: {str(e)}[/bold red]"
        )
