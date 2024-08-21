import base64
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
from .k8s import apply_kubernetes_yaml, create_namespace, get_mission


@click.group(name="scenarios")
def scenarios():
    """Manage scenarios on a running network"""


@scenarios.command()
def available():
    """
    List available scenarios in the Warnet Test Framework
    """
    console = Console()

    scenario_list = []
    for s in pkgutil.iter_modules(SCENARIOS.__path__):
        scenario_list.append(s.name)

    # Create the table
    table = Table(show_header=True, header_style="bold")
    table.add_column("Name")

    for scenario in scenario_list:
        table.add_row(scenario)
    console.print(table)


@scenarios.command(context_settings={"ignore_unknown_options": True})
@click.argument("scenario", type=str)
@click.argument("additional_args", nargs=-1, type=click.UNPROCESSED)
@click.option("--network", default="warnet", show_default=True)
def run(scenario, network, additional_args):
    """
    Run <scenario> from the Warnet Test Framework on [network] with optional arguments
    """

    # Use importlib.resources to get the scenario path
    scenario_package = "warnet.scenarios"
    scenario_filename = f"{scenario}.py"

    # Ensure the scenario file exists within the package
    with importlib.resources.path(scenario_package, scenario_filename) as scenario_path:
        scenario_path = str(scenario_path)  # Convert Path object to string

    if not os.path.exists(scenario_path):
        raise Exception(f"Scenario {scenario} not found at {scenario_path}.")

    with open(scenario_path) as file:
        scenario_text = file.read()

    name = f"commander-{scenario.replace('_', '')}-{int(time.time())}"

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
                } for tank in tankpods
            ]
    kubernetes_objects = [create_namespace()]
    kubernetes_objects.extend(
        [
            {
                "apiVersion": "v1",
                "kind": "ConfigMap",
                "metadata": {
                    "name": "warnetjson",
                    "namespace": "warnet",
                },
                "data": {"warnet.json": json.dumps(tanks)},
            },
            {
                "apiVersion": "v1",
                "kind": "ConfigMap",
                "metadata": {
                    "name": "scnaeriopy",
                    "namespace": "warnet",
                },
                "data": {"scenario.py": scenario_text},
            },
            {
                "apiVersion": "v1",
                "kind": "Pod",
                "metadata": {
                    "name": name,
                    "namespace": "warnet",
                    "labels": {"mission": "commander"},
                },
                "spec": {
                    "restartPolicy": "Never",
                    "containers": [
                        {
                            "name": name,
                            "image": "warnet-commander:latest",
                            "args": additional_args,
                            "imagePullPolicy": "Never",
                            "volumeMounts": [
                                {
                                    "name": "warnetjson",
                                    "mountPath": "warnet.json",
                                    "subPath": "warnet.json",
                                },
                                {
                                    "name": "scnaeriopy",
                                    "mountPath": "scenario.py",
                                    "subPath": "scenario.py",
                                },
                            ],
                        }
                    ],
                    "volumes": [
                        {"name": "warnetjson", "configMap": {"name": "warnetjson"}},
                        {"name": "scnaeriopy", "configMap": {"name": "scnaeriopy"}},
                    ],
                },
            },
        ]
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as temp_file:
        yaml.dump_all(kubernetes_objects, temp_file)
        temp_file_path = temp_file.name
    apply_kubernetes_yaml(temp_file_path)


@scenarios.command(context_settings={"ignore_unknown_options": True})
@click.argument("scenario_path", type=str)
@click.argument("additional_args", nargs=-1, type=click.UNPROCESSED)
@click.option("--name", type=str)
@click.option("--network", default="warnet", show_default=True)
def run_file(scenario_path, network, additional_args, name=""):
    """
    Run <scenario_path> from the Warnet Test Framework on [network] with optional arguments
    """
    if not scenario_path.endswith(".py"):
        print("Error. Currently only python scenarios are supported")
        sys.exit(1)
    scenario_name = name if name else os.path.splitext(os.path.basename(scenario_path))[0]
    scenario_base64 = ""
    with open(scenario_path, "rb") as f:
        scenario_base64 = base64.b64encode(f.read()).decode("utf-8")

    params = {
        "scenario_base64": scenario_base64,
        "scenario_name": scenario_name,
        "additional_args": additional_args,
        "network": network,
    }
    # TODO
    # print(rpc_call("scenarios_run_file", params))


@scenarios.command()
def active():
    """
    List running scenarios "name": "pid" pairs
    """
    commanders = get_mission("commander")
    if len(commanders) == 0:
        print("No scenarios running")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("Commander")
    table.add_column("Status")

    for commander in commanders:
        table.add_row(commander.metadata.name, commander.status.phase)

    console = Console()
    console.print(table)
