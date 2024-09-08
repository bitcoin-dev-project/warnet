import os
import subprocess
import sys

import click
import yaml


@click.command()
@click.argument("kube_config", type=str)
def auth(kube_config: str) -> None:
    """
    Authenticate with a warnet cluster using a kube config file
    """
    try:
        current_kubeconfig = os.environ.get("KUBECONFIG", os.path.expanduser("~/.kube/config"))
        combined_kubeconfig = (
            f"{current_kubeconfig}:{kube_config}" if current_kubeconfig else kube_config
        )
        os.environ["KUBECONFIG"] = combined_kubeconfig
        with open(kube_config) as file:
            content = yaml.safe_load(file)
            user = content["users"][0]
            user_name = user["name"]
            user_token = user["user"]["token"]
            current_context = content["current-context"]
        flatten_cmd = "kubectl config view --flatten"
        result_flatten = subprocess.run(
            flatten_cmd, shell=True, check=True, capture_output=True, text=True
        )
    except subprocess.CalledProcessError as e:
        click.secho("Error occurred while executing kubectl config view --flatten:", fg="red")
        click.secho(e.stderr, fg="red")
        sys.exit(1)

    if result_flatten.returncode == 0:
        with open(current_kubeconfig, "w") as file:
            file.write(result_flatten.stdout)
            click.secho(f"Authorization file written to: {current_kubeconfig}", fg="green")
    else:
        click.secho("Could not create authorization file", fg="red")
        click.secho(result_flatten.stderr, fg="red")
        sys.exit(result_flatten.returncode)

    try:
        update_cmd = f"kubectl config set-credentials {user_name} --token {user_token}"
        result_update = subprocess.run(
            update_cmd, shell=True, check=True, capture_output=True, text=True
        )
        if result_update.returncode != 0:
            click.secho("Could not update authorization file", fg="red")
            click.secho(result_flatten.stderr, fg="red")
            sys.exit(result_flatten.returncode)
    except subprocess.CalledProcessError as e:
        click.secho("Error occurred while executing kubectl config view --flatten:", fg="red")
        click.secho(e.stderr, fg="red")
        sys.exit(1)

    with open(current_kubeconfig) as file:
        contents = yaml.safe_load(file)

    with open(current_kubeconfig, "w") as file:
        contents["current-context"] = current_context
        yaml.safe_dump(contents, file)

    with open(current_kubeconfig) as file:
        contents = yaml.safe_load(file)
        click.secho(
            f"\nwarnet's current context is now set to: {contents['current-context']}", fg="green"
        )
