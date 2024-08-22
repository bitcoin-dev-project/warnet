import importlib
import json
import os
import pkgutil
import sys
import tempfile
import time

import click
import yaml
from rich import print
from rich.console import Console
from rich.table import Table

from warnet import scenarios as SCENARIOS

from .k8s import apply_kubernetes_yaml, get_mission, get_default_namespace


@click.group(name="scenarios")
def scenarios():
    """Manage scenarios on a running network"""


@scenarios.command()
def available():
    """
    List available scenarios in the Warnet Test Framework
    """
    console = Console()
    scenario_list = _available()

    # Create the table
    table = Table(show_header=True, header_style="bold")
    table.add_column("Name")
    table.add_column("Description")

    for scenario in scenario_list:
        table.add_row(*scenario)
    console.print(table)


def _available():
    # This ugly hack temporarily allows us to import the scenario modules
    # in the context in which they run: as __main__ from
    # the root directory of the commander container.
    scenarios_path = SCENARIOS.__path__
    sys.path.insert(0, scenarios_path[0])

    scenario_list = []
    for s in pkgutil.iter_modules(scenarios_path):
        module_name = f"warnet.scenarios.{s.name}"
        try:
            m = importlib.import_module(module_name)
            if hasattr(m, "cli_help"):
                scenario_list.append((s.name, m.cli_help()))
        except Exception as e:
            print(f"Ignoring module: {module_name} because {e}")

    # Clean up that ugly hack
    sys.path.pop(0)

    return scenario_list


@scenarios.command(context_settings={"ignore_unknown_options": True})
@click.argument("scenario", type=str)
@click.argument("additional_args", nargs=-1, type=click.UNPROCESSED)
def run(scenario: str, additional_args: tuple[str]):
    """
    Run <scenario> from the Warnet Test Framework with optional arguments
    """

    # Use importlib.resources to get the scenario path
    scenario_package = "warnet.scenarios"
    scenario_filename = f"{scenario}.py"

    # Ensure the scenario file exists within the package
    with importlib.resources.path(scenario_package, scenario_filename) as scenario_path:
        scenario_path = str(scenario_path)  # Convert Path object to string
    return run_scenario(scenario_path, additional_args)


@scenarios.command(context_settings={"ignore_unknown_options": True})
@click.argument("scenario_path", type=str)
@click.argument("additional_args", nargs=-1, type=click.UNPROCESSED)
def run_file(scenario_path: str, additional_args: tuple[str]):
    """
    Run <scenario_path> from the Warnet Test Framework with optional arguments
    """
    if not scenario_path.endswith(".py"):
        print("Error. Currently only python scenarios are supported")
        sys.exit(1)
    return run_scenario(scenario_path, additional_args)


def run_scenario(scenario_path: str, additional_args: tuple[str]):
    if not os.path.exists(scenario_path):
        raise Exception(f"Scenario file not found at {scenario_path}.")

    with open(scenario_path) as file:
        scenario_text = file.read()

    scenario_name = os.path.splitext(os.path.basename(scenario_path))[0]

    name = f"commander-{scenario_name.replace('_', '')}-{int(time.time())}"
    namespace = get_default_namespace()
    tankpods = get_mission("tank")
    tanks = [
        {
            "tank": tank.metadata.name,
            "chain": "regtest",
            "rpc_host": tank.status.pod_ip,
            "rpc_port": 18443,
            "rpc_user": "user",
            "rpc_password": "password",
            "init_peers": [],
        }
        for tank in tankpods
    ]
    kubernetes_objects = []
    kubernetes_objects.extend(
        [
            {
                "apiVersion": "v1",
                "kind": "ConfigMap",
                "metadata": {
                    "name": "warnetjson",
                    "namespace": namespace,
                },
                "data": {"warnet.json": json.dumps(tanks)},
            },
            {
                "apiVersion": "v1",
                "kind": "ConfigMap",
                "metadata": {
                    "name": "scenariopy",
                    "namespace": namespace,
                },
                "data": {"scenario.py": scenario_text},
            },
            {
                "apiVersion": "v1",
                "kind": "Pod",
                "metadata": {
                    "name": name,
                    "namespace": namespace,
                    "labels": {"mission": "commander"},
                },
                "spec": {
                    "restartPolicy": "Never",
                    "containers": [
                        {
                            "name": name,
                            "image": "bitcoindevproject/warnet-commander:latest",
                            "args": additional_args,
                            "volumeMounts": [
                                {
                                    "name": "warnetjson",
                                    "mountPath": "warnet.json",
                                    "subPath": "warnet.json",
                                },
                                {
                                    "name": "scenariopy",
                                    "mountPath": "scenario.py",
                                    "subPath": "scenario.py",
                                },
                            ],
                        }
                    ],
                    "volumes": [
                        {"name": "warnetjson", "configMap": {"name": "warnetjson"}},
                        {"name": "scenariopy", "configMap": {"name": "scenariopy"}},
                    ],
                },
            },
        ]
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as temp_file:
        yaml.dump_all(kubernetes_objects, temp_file)
        temp_file_path = temp_file.name
    apply_kubernetes_yaml(temp_file_path)


@scenarios.command()
def active():
    """
    List running scenarios "name": "pid" pairs
    """
    commanders = _active()
    if len(commanders) == 0:
        print("No scenarios running")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("Commander")
    table.add_column("Status")

    for commander in commanders:
        table.add_row(commander["commander"], commander["status"])

    console = Console()
    console.print(table)


def _active() -> list[str]:
    commanders = get_mission("commander")
    return [{"commander": c.metadata.name, "status": c.status.phase.lower()} for c in commanders]
