import io
import json
import os
import subprocess
import sys
import time
import zipapp
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import click
import inquirer
from inquirer.themes import GreenPassion
from kubernetes.client.models import V1Pod
from rich import print
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

from .constants import (
    BITCOINCORE_CONTAINER,
    COMMANDER_CHART,
    COMMANDER_CONTAINER,
    COMMANDER_MISSION,
    TANK_MISSION,
)
from .k8s import (
    can_delete_pods,
    delete_pod,
    get_default_namespace,
    get_default_namespace_or,
    get_mission,
    get_namespaces,
    get_pod,
    get_pods,
    pod_log,
    snapshot_bitcoin_datadir,
    wait_for_init,
    wait_for_pod,
    write_file_to_container,
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


@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Skip confirmations",
)
@click.command()
def down(force):
    """Bring down a running warnet quickly"""

    def uninstall_release(namespace, release_name):
        cmd = f"helm uninstall {release_name} --namespace {namespace} --wait=false"
        subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Initiated uninstall for: {release_name} in namespace {namespace}"

    def delete_pod(pod_name, namespace):
        cmd = f"kubectl delete pod --ignore-not-found=true {pod_name} -n {namespace} --grace-period=0 --force"
        subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Initiated deletion of pod: {pod_name} in namespace {namespace}"

    if not can_delete_pods():
        click.secho("You do not have permission to bring down the network.", fg="red")
        return

    namespaces = get_namespaces()
    release_list: list[dict[str, str]] = []
    for v1namespace in namespaces:
        namespace = v1namespace.metadata.name
        command = f"helm list --namespace {namespace} -o json"
        result = run_command(command)
        if result:
            releases = json.loads(result)
            for release in releases:
                release_list.append({"namespace": namespace, "name": release["name"]})

    if not force:
        affected_namespaces = set([entry["namespace"] for entry in release_list])
        namespace_listing = "\n  ".join(affected_namespaces)
        confirmed = "confirmed"
        click.secho("Preparing to bring down the running Warnet...", fg="yellow")
        click.secho("The listed namespaces will be affected:", fg="yellow")
        click.secho(f"  {namespace_listing}", fg="blue")

        proj_answers = inquirer.prompt(
            [
                inquirer.Confirm(
                    confirmed,
                    message=click.style(
                        "Do you want to bring down the running Warnet?", fg="yellow", bold=False
                    ),
                    default=False,
                ),
            ]
        )
        if not proj_answers:
            click.secho("Operation cancelled by user.", fg="yellow")
            sys.exit(0)
        if proj_answers[confirmed]:
            click.secho("Bringing down the warnet...", fg="yellow")
        else:
            click.secho("Operation cancelled by user", fg="yellow")
            sys.exit(0)

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []

        # Uninstall Helm releases
        for release in release_list:
            futures.append(
                executor.submit(uninstall_release, release["namespace"], release["name"])
            )

        # Delete remaining pods
        pods = get_pods()
        for pod in pods:
            futures.append(executor.submit(delete_pod, pod.metadata.name, pod.metadata.namespace))

        # Wait for all tasks to complete and print results
        for future in as_completed(futures):
            console.print(f"[yellow]{future.result()}[/yellow]")

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
@click.option(
    "--debug",
    is_flag=True,
    default=False,
    help="Stream scenario output and delete container when stopped",
)
@click.option(
    "--source_dir", type=click.Path(exists=True, file_okay=False, dir_okay=True), required=False
)
@click.argument("additional_args", nargs=-1, type=click.UNPROCESSED)
@click.option("--namespace", default=None, show_default=True)
def run(
    scenario_file: str,
    debug: bool,
    source_dir,
    additional_args: tuple[str],
    namespace: Optional[str],
):
    """
    Run a scenario from a file.
    Pass `-- --help` to get individual scenario help
    """
    namespace = get_default_namespace_or(namespace)

    scenario_path = Path(scenario_file).resolve()
    scenario_dir = scenario_path.parent if not source_dir else Path(source_dir).resolve()
    scenario_name = scenario_path.stem

    if additional_args and ("--help" in additional_args or "-h" in additional_args):
        return subprocess.run([sys.executable, scenario_path, "--help"])

    # Collect tank data for warnet.json
    name = f"commander-{scenario_name.replace('_', '')}-{int(time.time())}"
    tankpods = get_mission("tank")
    tanks = [
        {
            "tank": tank.metadata.name,
            "chain": tank.metadata.labels["chain"],
            "rpc_host": tank.status.pod_ip,
            "rpc_port": int(tank.metadata.labels["RPCPort"]),
            "rpc_user": "user",
            "rpc_password": tank.metadata.labels["rpcpassword"],
            "init_peers": [],
        }
        for tank in tankpods
    ]

    # Encode tank data for warnet.json
    warnet_data = json.dumps(tanks).encode()

    # Create in-memory buffer to store python archive instead of writing to disk
    archive_buffer = io.BytesIO()

    # No need to copy the entire scenarios/ directory into the archive
    def filter(path):
        if any(needle in str(path) for needle in [".pyc", ".csv", ".DS_Store"]):
            return False
        if any(
            needle in str(path)
            for needle in ["__init__.py", "commander.py", "test_framework", scenario_path.name]
        ):
            print(f"Including: {path}")
            return True
        return False

    # In case the scenario file is not in the root of the archive directory,
    # we need to specify its relative path as a submodule
    # First get the path of the file relative to the source directory
    relative_path = scenario_path.relative_to(scenario_dir)
    # Remove the '.py' extension
    relative_name = relative_path.with_suffix("")
    # Replace path separators with dots and pray the user included __init__.py
    module_name = ".".join(relative_name.parts)
    # Compile python archive
    zipapp.create_archive(
        source=scenario_dir,
        target=archive_buffer,
        main=f"{module_name}:main",
        compressed=True,
        filter=filter,
    )

    # Encode the binary data as Base64
    archive_buffer.seek(0)
    archive_data = archive_buffer.read()

    # Start the commander pod with python and init containers
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
        ]

        # Add additional arguments
        if additional_args:
            helm_command.extend(["--set", f"args={' '.join(additional_args)}"])

        helm_command.extend([name, COMMANDER_CHART])

        # Execute Helm command
        result = subprocess.run(helm_command, check=True, capture_output=True, text=True)

        if result.returncode == 0:
            print(f"Successfully deployed scenario commander: {scenario_name}")
            print(f"Commander pod name: {name}")
        else:
            print(f"Failed to deploy scenario commander: {scenario_name}")
            print(f"Error: {result.stderr}")

    except subprocess.CalledProcessError as e:
        print(f"Failed to deploy scenario commander: {scenario_name}")
        print(f"Error: {e.stderr}")

    # upload scenario files and network data to the init container
    wait_for_init(name, namespace=namespace)
    if write_file_to_container(
        name, "init", "/shared/warnet.json", warnet_data, namespace=namespace
    ) and write_file_to_container(
        name, "init", "/shared/archive.pyz", archive_data, namespace=namespace
    ):
        print(f"Successfully uploaded scenario data to commander: {scenario_name}")

    if debug:
        print("Waiting for commander pod to start...")
        wait_for_pod(name, namespace=namespace)
        _logs(pod_name=name, follow=True, namespace=namespace)
        print("Deleting pod...")
        delete_pod(name, namespace=namespace)


@click.command()
@click.argument("pod_name", type=str, default="")
@click.option("--follow", "-f", is_flag=True, default=False, help="Follow logs")
@click.option("--namespace", type=str, default="default", show_default=True)
def logs(pod_name: str, follow: bool, namespace: str):
    """Show the logs of a pod"""
    return _logs(pod_name, follow, namespace)


def _logs(pod_name: str, follow: bool, namespace: Optional[str] = None):
    namespace = get_default_namespace_or(namespace)

    def format_pods(pods: list[V1Pod]) -> list[str]:
        sorted_pods = sorted(pods, key=lambda pod: pod.metadata.creation_timestamp, reverse=True)
        return [f"{pod.metadata.name}: {pod.metadata.namespace}" for pod in sorted_pods]

    if pod_name == "":
        try:
            pod_list = []
            formatted_commanders = format_pods(get_mission(COMMANDER_MISSION))
            formatted_tanks = format_pods(get_mission(TANK_MISSION))
            pod_list.extend(formatted_commanders)
            pod_list.extend(formatted_tanks)

        except Exception as e:
            print(f"Could not fetch any pods in namespace ({namespace}): {e}")
            return

        if not pod_list:
            print(f"Could not fetch any pods in namespace ({namespace})")
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
            pod_name, pod_namespace = selected["pod"].split(": ")
        else:
            return  # cancelled by user

    try:
        pod = get_pod(pod_name, namespace=pod_namespace)
        eligible_container_names = [BITCOINCORE_CONTAINER, COMMANDER_CONTAINER]
        available_container_names = [container.name for container in pod.spec.containers]
        container_name = next(
            (
                container_name
                for container_name in available_container_names
                if container_name in eligible_container_names
            ),
            None,
        )
        if not container_name:
            print("Could not determine primary container.")
            return
    except Exception as e:
        print(f"Error getting pods. Could not determine primary container: {e}")
        return

    try:
        stream = pod_log(
            pod_name, container_name=container_name, namespace=pod_namespace, follow=follow
        )
        for line in stream:
            click.echo(line.decode("utf-8").rstrip())
    except Exception as e:
        print(e)
    except KeyboardInterrupt:
        print("Interrupted streaming log!")


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
