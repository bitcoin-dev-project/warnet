import os
import subprocess
import sys

import click
from rich import print as richprint

from .graph import graph
from .image import image
from .network import network
from .rpc import rpc_call
from .scenarios import scenarios


@click.group()
def cli():
    pass


cli.add_command(graph)
cli.add_command(image)
cli.add_command(network)
cli.add_command(scenarios)


@cli.command(name="help")
@click.argument("commands", required=False, nargs=-1)
@click.pass_context
def help_command(ctx, commands):
    """
    Display help information for the given [command] (and sub-command).
    If no command is given, display help for the main CLI.
    """
    if not commands:
        # Display help for the main CLI
        richprint(ctx.parent.get_help())
        return

    # Recurse down the subcommands, fetching the command object for each
    cmd_obj = cli
    for command in commands:
        cmd_obj = cmd_obj.get_command(ctx, command)
        if cmd_obj is None:
            richprint(f'Unknown command "{command}" in {commands}')
            return
        ctx = click.Context(cmd_obj, info_name=command, parent=ctx)

    if cmd_obj is None:
        richprint(f"Unknown command: {commands}")
        return

    # Get the help info
    help_info = cmd_obj.get_help(ctx).strip()
    # Get rid of the duplication
    help_info = help_info.replace("Usage: warcli help [COMMANDS]...", "Usage: warcli", 1)
    richprint(help_info)


cli.add_command(help_command)


@cli.command(context_settings={"ignore_unknown_options": True})
@click.argument("node", type=int)
@click.argument("method", type=str)
@click.argument("params", type=str, nargs=-1)  # this will capture all remaining arguments
@click.option("--network", default="warnet", show_default=True)
def rpc(node, method, params, network):
    """
    Call bitcoin-cli <method> [params] on <node> in [network]
    """
    print(
        rpc_call(
            "tank_bcli", {"network": network, "node": node, "method": method, "params": params}
        )
    )


@cli.command(context_settings={"ignore_unknown_options": True})
@click.argument("node", type=int)
@click.argument("command", type=str, required=True, nargs=-1)
@click.option("--network", default="warnet", show_default=True, type=str)
def lncli(node: int, command: tuple, network: str):
    """
    Call lightning cli <command> on <node> in [network]
    """
    print(
        rpc_call(
            "tank_lncli",
            {"network": network, "node": node, "command": command},
        )
    )


@cli.command(context_settings={"ignore_unknown_options": True})
@click.argument("node", type=int)
@click.option("--network", default="warnet", show_default=True, type=str)
def ln_pub_key(node: int, network: str):
    """
    Get lightning node pub key on <node> in [network]
    """
    print(
        rpc_call(
            "tank_ln_pub_key",
            {"network": network, "node": node},
        )
    )


@cli.command()
@click.argument("node", type=int, required=True)
@click.option("--network", default="warnet", show_default=True)
def debug_log(node, network):
    """
    Fetch the Bitcoin Core debug log from <node> in [network]
    """
    print(rpc_call("tank_debug_log", {"node": node, "network": network}))


@cli.command()
@click.argument("node_a", type=int, required=True)
@click.argument("node_b", type=int, required=True)
@click.option("--network", default="warnet", show_default=True)
def messages(node_a, node_b, network):
    """
    Fetch messages sent between <node_a> and <node_b> in [network]
    """
    print(rpc_call("tank_messages", {"network": network, "node_a": node_a, "node_b": node_b}))


@cli.command()
@click.argument("pattern", type=str, required=True)
@click.option("--network", default="warnet", show_default=True)
def grep_logs(pattern, network):
    """
    Grep combined logs via fluentd using regex <pattern>
    """
    print(rpc_call("logs_grep", {"network": network, "pattern": pattern}))


def run_command(command, stream_output=False):
    if stream_output:
        process = subprocess.Popen(
            ["/bin/bash", "-c", command],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )

        for line in iter(process.stdout.readline, ""):
            print(line, end="")

        process.stdout.close()
        return_code = process.wait()

        if return_code != 0:
            print(f"Command failed with return code {return_code}")
            return False
        return True
    else:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, executable="/bin/bash"
        )
        if result.returncode != 0:
            print(f"Error: {result.stderr}")
            return False
        print(result.stdout)
        return True


@cli.command()
def start():
    """Setup and start the RPC in dev mode with minikube"""
    script_content = """
    #!/usr/bin/env bash
    set -euxo pipefail

    # Function to check if minikube is running
    check_minikube() {
        minikube status | grep -q "Running" && echo "Minikube is already running" || minikube start --memory=max --cpus=max --mount --mount-string="$PWD:/mnt/src"
    }

    # Function to check if warnet-rpc container is already running
    check_warnet_rpc() {
        if kubectl get pods --all-namespaces | grep -q "bitcoindevproject/warnet-rpc"; then
            echo "warnet-rpc already running in minikube"
            exit 1
        fi
    }

    # Check minikube status
    check_minikube

    # Build image in local registry and load into minikube
    docker build -t warnet/dev -f src/warnet/templates/rpc/Dockerfile_rpc_dev . --load
    minikube image load warnet/dev

    # Setup k8s
    kubectl apply -f src/warnet/templates/rpc/namespace.yaml
    kubectl apply -f src/warnet/templates/rpc/rbac-config.yaml
    kubectl apply -f src/warnet/templates/rpc/warnet-rpc-service.yaml
    kubectl apply -f src/warnet/templates/rpc/warnet-rpc-statefulset-dev.yaml
    kubectl config set-context --current --namespace=warnet

    # Check for warnet-rpc container
    check_warnet_rpc

    until kubectl get pod rpc-0 --namespace=warnet; do
       echo "Waiting for server to find pod rpc-0..."
       sleep 4
    done

    echo "⏲️ This could take a minute or so."
    kubectl wait --for=condition=Ready --timeout=2m pod rpc-0

    echo Done...
    """
    res = run_command(script_content, stream_output=True)
    if res:
        _port_start_internal()


@cli.command()
def stop():
    """Stop the warnet server and tear down the cluster"""
    script_content = """
    #!/usr/bin/env bash
    set -euxo pipefail

    kubectl delete namespace warnet
    kubectl delete namespace warnet-logging
    kubectl config set-context --current --namespace=default

    minikube image rm warnet/dev
    """
    run_command(script_content, stream_output=True)
    _port_stop_internal()


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


def _port_start_internal():
    command = "kubectl port-forward svc/rpc 9276:9276"
    run_detached_process(command)
    print(
        "Port forwarding on port 9276 started in the background. Use 'warcli' (or 'kubectl') to manage the warnet."
    )


@cli.command()
def port_start():
    """Port forward (runs as a detached process)"""
    _port_start_internal()


def _port_stop_internal():
    if is_windows():
        os.system("taskkill /F /IM kubectl.exe")
    else:
        os.system("pkill -f 'kubectl port-forward svc/rpc 9276:9276'")
    print("Port forwarding stopped.")


@cli.command()
def port_stop():
    """Stop the port forwarding process"""
    _port_stop_internal()


if __name__ == "__main__":
    cli()
