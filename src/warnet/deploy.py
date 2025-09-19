import json
import subprocess
import sys
import tempfile
from multiprocessing import Process
from pathlib import Path
from typing import Optional

import click
import yaml

from .constants import (
    BITCOIN_CHART_LOCATION,
    CADDY_CHART,
    DEFAULTS_FILE,
    DEFAULTS_NAMESPACE_FILE,
    FORK_OBSERVER_CHART,
    FORK_OBSERVER_RPC_PASSWORD,
    FORK_OBSERVER_RPC_USER,
    HELM_COMMAND,
    INGRESS_HELM_COMMANDS,
    LOGGING_CRD_COMMANDS,
    LOGGING_HELM_COMMANDS,
    LOGGING_NAMESPACE,
    NAMESPACES_CHART_LOCATION,
    NAMESPACES_FILE,
    NETWORK_FILE,
    PLUGIN_ANNEX,
    SCENARIOS_DIR,
    WARGAMES_NAMESPACE_PREFIX,
    AnnexMember,
    HookValue,
    WarnetContent,
)
from .control import _logs, _run
from .k8s import (
    get_default_namespace,
    get_default_namespace_or,
    get_mission,
    get_namespaces_by_type,
    wait_for_ingress_controller,
    wait_for_pod_ready,
)
from .process import run_command, stream_command

HINT = "\nAre you trying to run a scenario? See `warnet run --help`"


def validate_directory(ctx, param, value):
    directory = Path(value)
    if not directory.is_dir():
        raise click.BadParameter(f"'{value}' is not a valid directory.{HINT}")
    if not (directory / NETWORK_FILE).exists() and not (directory / NAMESPACES_FILE).exists():
        raise click.BadParameter(
            f"'{value}' does not contain a valid network.yaml or namespaces.yaml file.{HINT}"
        )
    return directory


@click.command(context_settings={"ignore_unknown_options": True})
@click.argument(
    "directory",
    type=click.Path(exists=True),
    callback=validate_directory,
)
@click.option("--debug", is_flag=True)
@click.option("--namespace", type=str, help="Specify a namespace in which to deploy the network")
@click.option("--to-all-users", is_flag=True, help="Deploy network to all user namespaces")
@click.argument("unknown_args", nargs=-1)
def deploy(directory, debug, namespace, to_all_users, unknown_args):
    """Deploy a warnet with topology loaded from <directory>"""
    if unknown_args:
        raise click.BadParameter(f"Unknown args: {unknown_args}{HINT}")

    _deploy(directory, debug, namespace, to_all_users)


def _deploy(directory, debug, namespace, to_all_users):
    """Deploy a warnet with topology loaded from <directory>"""
    directory = Path(directory)

    if to_all_users:
        namespaces = get_namespaces_by_type(WARGAMES_NAMESPACE_PREFIX)
        processes = []
        for namespace in namespaces:
            p = Process(target=_deploy, args=(directory, debug, namespace.metadata.name, False))
            p.start()
            processes.append(p)
        for p in processes:
            p.join()
        return

    if (directory / NETWORK_FILE).exists():
        run_plugins(directory, HookValue.PRE_DEPLOY, namespace)

        processes = []
        # Deploy logging CRD first to avoid synchronisation issues
        deploy_logging_crd(directory, debug)

        logging_process = Process(target=deploy_logging_stack, args=(directory, debug))
        logging_process.start()
        processes.append(logging_process)

        run_plugins(directory, HookValue.PRE_NETWORK, namespace)

        network_process = Process(target=deploy_network, args=(directory, debug, namespace))
        network_process.start()

        ingress_process = Process(target=deploy_ingress, args=(directory, debug))
        ingress_process.start()
        processes.append(ingress_process)

        caddy_process = Process(target=deploy_caddy, args=(directory, debug))
        caddy_process.start()
        processes.append(caddy_process)

        # Wait for the network process to complete
        network_process.join()

        run_plugins(directory, HookValue.POST_NETWORK, namespace)

        # Start the fork observer process immediately after network process completes
        fork_observer_process = Process(target=deploy_fork_observer, args=(directory, debug))
        fork_observer_process.start()
        processes.append(fork_observer_process)

        # Wait for all other processes to complete
        for p in processes:
            p.join()

        run_plugins(directory, HookValue.POST_DEPLOY, namespace)

    elif (directory / NAMESPACES_FILE).exists():
        deploy_namespaces(directory)
    else:
        click.echo(
            "Error: Neither network.yaml nor namespaces.yaml found in the specified directory."
        )


def run_plugins(directory, hook_value: HookValue, namespace, annex: Optional[dict] = None):
    """Run the plugin commands within a given hook value"""

    network_file_path = directory / NETWORK_FILE

    with network_file_path.open() as f:
        network_file = yaml.safe_load(f) or {}
        if not isinstance(network_file, dict):
            raise ValueError(f"Invalid network file structure: {network_file_path}")

    processes = []

    plugins_section = network_file.get("plugins", {})
    hook_section = plugins_section.get(hook_value.value, {})
    for plugin_name, plugin_content in hook_section.items():
        match (plugin_name, plugin_content):
            case (str(), dict()):
                try:
                    entrypoint_path = Path(plugin_content.get("entrypoint"))
                except Exception as err:
                    raise SyntaxError("Each plugin must have an 'entrypoint'") from err

                warnet_content = {
                    WarnetContent.HOOK_VALUE.value: hook_value.value,
                    WarnetContent.NAMESPACE.value: namespace,
                    PLUGIN_ANNEX: annex,
                }

                cmd = (
                    f"{sys.executable} {network_file_path.parent / entrypoint_path / Path('plugin.py')} entrypoint "
                    f"'{json.dumps(plugin_content)}' '{json.dumps(warnet_content)}'"
                )
                print(
                    f"Queuing {hook_value.value} plugin command: {plugin_name} with {plugin_content}"
                )

                process = Process(target=run_command, args=(cmd,))
                processes.append(process)

            case _:
                print(
                    f"The following plugin command does not match known plugin command structures: {plugin_name} {plugin_content}"
                )
                sys.exit(1)

    if processes:
        print(f"Starting {hook_value.value} plugins")

        for process in processes:
            process.start()

        for process in processes:
            process.join()

        print(f"Completed {hook_value.value} plugins")


def check_logging_required(directory: Path):
    # check if node-defaults has logging or metrics enabled
    default_file_path = directory / DEFAULTS_FILE
    with default_file_path.open() as f:
        default_file = yaml.safe_load(f)
    if default_file.get("collectLogs", False):
        return True
    if default_file.get("metricsExport", False):
        return True
    if default_file.get("lnd", {}).get("metricsExport"):
        return True

    # check to see if individual nodes have logging enabled
    network_file_path = directory / NETWORK_FILE
    with network_file_path.open() as f:
        network_file = yaml.safe_load(f)

    nodes = network_file.get("nodes") or []
    for node in nodes:
        if node.get("collectLogs", False):
            return True
        if node.get("metricsExport", False):
            return True
        if node.get("lnd", {}).get("metricsExport"):
            return True

    return False


def deploy_logging_crd(directory: Path, debug: bool) -> bool:
    """
    This function exists so we can parallelise the rest of the loggin stack
    installation
    """
    if not check_logging_required(directory):
        return False

    click.echo(
        "Found collectLogs or metricsExport in network definition, Deploying logging stack CRD"
    )

    for command in LOGGING_CRD_COMMANDS:
        if not stream_command(command):
            print(f"Failed to run Helm command: {command}")
            return False
    return True


def deploy_logging_stack(directory: Path, debug: bool) -> bool:
    if not check_logging_required(directory):
        return False

    click.echo("Deploying logging stack")

    for command in LOGGING_HELM_COMMANDS:
        if not stream_command(command):
            print(f"Failed to run Helm command: {command}")
            return False
    return True


def deploy_caddy(directory: Path, debug: bool):
    network_file_path = directory / NETWORK_FILE
    with network_file_path.open() as f:
        network_file = yaml.safe_load(f)

    namespace = LOGGING_NAMESPACE
    # TODO: get this from the helm chart
    name = "caddy"

    # Only start if configured in the network file
    if not network_file.get(name, {}).get("enabled", False):
        return

    # configure reverse proxy to webservers in the network
    services = []
    # built-in services
    if check_logging_required(directory):
        services.append(
            {"title": "Grafana", "path": "/grafana/", "host": "loki-grafana", "port": 80}
        )
    if network_file.get("fork_observer", {}).get("enabled", False):
        services.append(
            {
                "title": "Fork Observer",
                "path": "/fork-observer/",
                "host": "fork-observer",
                "port": 2323,
            }
        )
    # add any extra services
    services += network_file.get("services", {})

    click.echo(f"Adding services to dashboard: {json.dumps(services, indent=2)}")

    cmd = (
        f"{HELM_COMMAND} {name} {CADDY_CHART} "
        f"--namespace {namespace} --create-namespace "
        f"--set-json services='{json.dumps(services)}'"
    )
    if debug:
        cmd += " --debug"

    if not stream_command(cmd):
        click.echo(f"Failed to run Helm command: {cmd}")
        return

    wait_for_pod_ready(name, namespace)
    click.echo("\nTo access the warnet dashboard run:\n  warnet dashboard")


def deploy_ingress(directory: Path, debug: bool):
    # Deploy ingress if either logging or fork observer is enabled
    network_file_path = directory / NETWORK_FILE
    with network_file_path.open() as f:
        network_file = yaml.safe_load(f)
    # Only start if caddy is enabled in the network file
    if not network_file.get("caddy", {}).get("enabled", False):
        return
    click.echo("Deploying ingress controller")

    for command in INGRESS_HELM_COMMANDS:
        if not stream_command(command):
            print(f"Failed to run Helm command: {command}")
            return False

    wait_for_ingress_controller()

    return True


def deploy_fork_observer(directory: Path, debug: bool) -> bool:
    network_file_path = directory / NETWORK_FILE
    with network_file_path.open() as f:
        network_file = yaml.safe_load(f)

    # Only start if configured in the network file
    if not network_file.get("fork_observer", {}).get("enabled", False):
        return False

    default_namespace = get_default_namespace()
    namespace = LOGGING_NAMESPACE
    cmd = f"{HELM_COMMAND} 'fork-observer' {FORK_OBSERVER_CHART} --namespace {namespace} --create-namespace"
    if debug:
        cmd += " --debug"

    temp_override_file_path = ""
    override_string = ""

    # Add an entry for each node in the graph
    for i, tank in enumerate(get_mission("tank")):
        node_name = tank.metadata.name
        for container in tank.spec.containers:
            if container.name == "bitcoincore":
                for port in container.ports:
                    if port.name == "rpc":
                        rpcport = port.container_port
                    if port.name == "p2p":
                        p2pport = port.container_port
        node_config = f"""
[[networks.nodes]]
id = {i}
name = "{node_name}"
description = "{node_name}.{default_namespace}.svc:{int(p2pport)}"
rpc_host = "{node_name}.{default_namespace}.svc"
rpc_port = {int(rpcport)}
rpc_user = "{FORK_OBSERVER_RPC_USER}"
rpc_password = "{FORK_OBSERVER_RPC_PASSWORD}"
"""

        override_string += node_config

    # Create yaml string using multi-line string format
    override_string = override_string.strip()
    v = {"config": override_string}
    v["configQueryinterval"] = network_file.get("fork_observer", {}).get("configQueryinterval", 20)
    yaml_string = yaml.dump(v, default_style="|", default_flow_style=False)

    # Dump to yaml tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as temp_file:
        temp_file.write(yaml_string)
        temp_override_file_path = Path(temp_file.name)

    cmd = f"{cmd} -f {temp_override_file_path}"

    if not stream_command(cmd):
        click.echo(f"Failed to run Helm command: {cmd}")
        return False
    return True


def deploy_network(directory: Path, debug: bool = False, namespace: Optional[str] = None):
    network_file_path = directory / NETWORK_FILE
    namespace = get_default_namespace_or(namespace)

    with network_file_path.open() as f:
        network_file = yaml.safe_load(f)

    needs_ln_init = False
    supported_ln_projects = ["lnd", "cln"]
    for node in network_file["nodes"]:
        ln_config = node.get("ln", {})
        for key in supported_ln_projects:
            if ln_config.get(key, False) and key in node and "channels" in node[key]:
                needs_ln_init = True
                break
        if needs_ln_init:
            break

    default_file_path = directory / DEFAULTS_FILE
    with default_file_path.open() as f:
        default_file = yaml.safe_load(f)
    if any(default_file.get("ln", {}).get(key, False) for key in supported_ln_projects):
        needs_ln_init = True

    processes = []
    for node in network_file["nodes"]:
        p = Process(target=deploy_single_node, args=(node, directory, debug, namespace))
        p.start()
        processes.append(p)

    for p in processes:
        p.join()

    if needs_ln_init:
        name = _run(
            scenario_file=SCENARIOS_DIR / "ln_init.py",
            debug=False,
            source_dir=SCENARIOS_DIR,
            additional_args=None,
            admin=True,
            namespace=namespace,
        )
        wait_for_pod_ready(name, namespace=namespace)
        _logs(pod_name=name, follow=True, namespace=namespace)


def deploy_single_node(node, directory: Path, debug: bool, namespace: str):
    defaults_file_path = directory / DEFAULTS_FILE
    click.echo(f"Deploying node: {node.get('name')}")
    temp_override_file_path = ""
    try:
        node_name = node.get("name")
        node_config_override = {k: v for k, v in node.items() if k != "name"}

        defaults_file_path = directory / DEFAULTS_FILE
        cmd = f"{HELM_COMMAND} {node_name} {BITCOIN_CHART_LOCATION} --namespace {namespace} -f {defaults_file_path}"
        if debug:
            cmd += " --debug"

        if node_config_override:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as temp_file:
                yaml.dump(node_config_override, temp_file)
                temp_override_file_path = Path(temp_file.name)
            cmd = f"{cmd} -f {temp_override_file_path}"

        run_plugins(
            directory, HookValue.PRE_NODE, namespace, annex={AnnexMember.NODE_NAME.value: node_name}
        )

        if not stream_command(cmd):
            click.echo(f"Failed to run Helm command: {cmd}")
            return

        run_plugins(
            directory,
            HookValue.POST_NODE,
            namespace,
            annex={AnnexMember.NODE_NAME.value: node_name},
        )

    except Exception as e:
        click.echo(f"Error: {e}")
        return
    finally:
        if temp_override_file_path:
            Path(temp_override_file_path).unlink()


def deploy_namespaces(directory: Path):
    namespaces_file_path = directory / NAMESPACES_FILE
    defaults_file_path = directory / DEFAULTS_NAMESPACE_FILE

    with namespaces_file_path.open() as f:
        namespaces_file = yaml.safe_load(f)

    names = [n.get("name") for n in namespaces_file["namespaces"]]
    for n in names:
        if not n.startswith(WARGAMES_NAMESPACE_PREFIX):
            click.secho(
                f"Failed to create namespace: {n}. Namespaces must start with a '{WARGAMES_NAMESPACE_PREFIX}' prefix.",
                fg="red",
            )
            return

    processes = []
    for namespace in namespaces_file["namespaces"]:
        p = Process(target=deploy_single_namespace, args=(namespace, defaults_file_path))
        p.start()
        processes.append(p)

    for p in processes:
        p.join()


def deploy_single_namespace(namespace, defaults_file_path: Path):
    click.echo(f"Deploying namespace: {namespace.get('name')}")
    temp_override_file_path = ""
    try:
        namespace_name = namespace.get("name")
        namespace_config_override = {k: v for k, v in namespace.items() if k != "name"}

        cmd = f"{HELM_COMMAND} {namespace_name} {NAMESPACES_CHART_LOCATION} -f {defaults_file_path}"

        if namespace_config_override:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as temp_file:
                yaml.dump(namespace_config_override, temp_file)
                temp_override_file_path = Path(temp_file.name)
            cmd = f"{cmd} -f {temp_override_file_path}"

        if not stream_command(cmd):
            click.echo(f"Failed to run Helm command: {cmd}")
            return
    except Exception as e:
        click.echo(f"Error: {e}")
        return
    finally:
        if temp_override_file_path:
            Path(temp_override_file_path).unlink()


def is_windows():
    return sys.platform.startswith("win")


def run_detached_process(command):
    if is_windows():
        # For Windows, use CREATE_NEW_PROCESS_GROUP and DETACHED_PROCESS
        subprocess.Popen(
            command,
            shell=True,
            stdin=None,
            stdout=None,
            stderr=None,
            close_fds=True,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
        )
    else:
        # For Unix-like systems, use nohup and redirect output
        command = f"nohup {command} > /dev/null 2>&1 &"
        subprocess.Popen(command, shell=True, stdin=None, stdout=None, stderr=None, close_fds=True)

    print(f"Started detached process: {command}")
