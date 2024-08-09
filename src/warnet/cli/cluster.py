import os
import subprocess
import sys
from importlib.resources import files

import click

MANIFEST_PATH = files("manifests")
RPC_PATH = files("images").joinpath("rpc")

SCRIPTS_PATH = files("scripts")
START_SCRIPT = SCRIPTS_PATH / "start.sh"
DEPLOY_SCRIPT = SCRIPTS_PATH / "deploy.sh"
INSTALL_LOGGING_SCRIPT = SCRIPTS_PATH / "install_logging.sh"
CONNECT_LOGGING_SCRIPT = SCRIPTS_PATH / "connect_logging.sh"


@click.group(name="cluster", chain=True)
def cluster():
    """Start, configure and stop a warnet k8s cluster\n
    \b
    Supports chaining, e.g:
      warcli cluster deploy
      warcli cluster teardown
    """
    pass


def run_command(command, stream_output=False, env=None):
    # Merge the current environment with the provided env
    full_env = os.environ.copy()
    if env:
        # Convert all env values to strings (only a safeguard)
        env = {k: str(v) for k, v in env.items()}
        full_env.update(env)

    if stream_output:
        process = subprocess.Popen(
            ["/bin/bash", "-c", command],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
            env=full_env,
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


@cluster.command()
@click.option("--clean", is_flag=True, help="Remove configuration files")
def setup_minikube(clean):
    """Configure a local minikube cluster"""
    memory = click.prompt(
        "How much RAM should we assign to the minikube cluster? (MB)",
        type=int,
        default=4000,
    )
    cpu = click.prompt(
        "How many CPUs should we assign to the minikube cluster?", type=int, default=4
    )
    env = {"WAR_MEM": str(memory), "WAR_CPU": str(cpu), "WAR_RPC": RPC_PATH}
    run_command(SCRIPTS_PATH / "setup_minikube.sh", stream_output=True, env=env)


# TODO: Add a --dev flag to this
@cluster.command()
@click.option("--dev", is_flag=True, help="Remove configuration files")
def deploy(dev: bool):
    """Deploy Warnet using the current kubectl-configured cluster"""
    env = {"WAR_MANIFESTS": str(MANIFEST_PATH), "WAR_RPC": RPC_PATH}
    if dev:
        env["WAR_DEV"] = 1
    res = run_command(SCRIPTS_PATH / "deploy.sh", stream_output=True, env=env)
    if res:
        _port_start_internal()


@cluster.command()
def teardown():
    """Stop the warnet server and tear down the cluster"""
    run_command(SCRIPTS_PATH / "stop.sh", stream_output=True)
    _port_stop_internal()


@cluster.command()
def deploy_logging():
    """Deploy logging configurations to the cluster using helm"""
    run_command(SCRIPTS_PATH / "install_logging.sh", stream_output=True)


@cluster.command()
def connect_logging():
    """Connect kubectl to cluster logging"""
    run_command(CONNECT_LOGGING_SCRIPT, stream_output=True)


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


@cluster.command()
def port_start():
    """Port forward (runs as a detached process)"""
    _port_start_internal()


def _port_stop_internal():
    if is_windows():
        os.system("taskkill /F /IM kubectl.exe")
    else:
        os.system("pkill -f 'kubectl port-forward svc/rpc 9276:9276'")
    print("Port forwarding stopped.")


@cluster.command()
def port_stop():
    """Stop the port forwarding process"""
    _port_stop_internal()
