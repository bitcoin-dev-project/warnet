import os
import subprocess
from pathlib import Path

import click
from rich import print as richprint

from .constants import NETWORK_DIR
from .namespaces import copy_namespaces_defaults, namespaces
from .network import copy_network_defaults


@click.group(name="admin", hidden=True)
def admin():
    """Admin commands for warnet project management"""
    pass


admin.add_command(namespaces)


@admin.command()
def init():
    """Initialize a warnet project in the current directory"""
    current_dir = os.getcwd()
    if os.listdir(current_dir):
        richprint("[yellow]Warning: Current directory is not empty[/yellow]")
        if not click.confirm("Do you want to continue?", default=True):
            return

    copy_network_defaults(Path(current_dir))
    copy_namespaces_defaults(Path(current_dir))
    richprint(
        f"[green]Copied network and namespace example files to {Path(current_dir) / NETWORK_DIR.name}[/green]"
    )
    richprint(f"[green]Created warnet project structure in {current_dir}[/green]")


# Get kubectl values
def get_kubectl_value(jsonpath):
    return subprocess.check_output(
        ["kubectl", "config", "view", "--minify", "-o", f"jsonpath={jsonpath}"]
    ).decode("utf-8")


# Get all namespaces that start with "warnet-"
def get_warnet_namespaces():
    namespaces = (
        subprocess.check_output(
            ["kubectl", "get", "namespaces", "-o", "jsonpath={.items[*].metadata.name}"]
        )
        .decode("utf-8")
        .split()
    )
    return [ns for ns in namespaces if ns.startswith("warnet-")]


# Get all service accounts for a given namespace
def get_service_accounts(namespace):
    return (
        subprocess.check_output(
            [
                "kubectl",
                "get",
                "serviceaccounts",
                "-n",
                namespace,
                "-o",
                "jsonpath={.items[*].metadata.name}",
            ]
        )
        .decode("utf-8")
        .split()
    )


@admin.command()
@click.option(
    "--kubeconfig-dir",
    default="kubeconfigs",
    help="Directory to store kubeconfig files (default: kubeconfigs)",
)
@click.option(
    "--token-duration",
    default=172800,
    type=int,
    help="Duration of the token in seconds (default: 48 hours)",
)
def create_kubeconfigs(kubeconfig_dir, token_duration):
    """Create kubeconfig files for all ServiceAccounts in namespaces starting with 'warnet-'."""
    kubeconfig_dir = os.path.expanduser(kubeconfig_dir)

    cluster_name = get_kubectl_value("{.clusters[0].name}")
    cluster_server = get_kubectl_value("{.clusters[0].cluster.server}")
    cluster_ca = get_kubectl_value("{.clusters[0].cluster.certificate-authority-data}")

    os.makedirs(kubeconfig_dir, exist_ok=True)

    # Get all namespaces that start with "warnet-"
    warnet_namespaces = get_warnet_namespaces()

    for namespace in warnet_namespaces:
        click.echo(f"Processing namespace: {namespace}")
        service_accounts = get_service_accounts(namespace)

        for sa in service_accounts:
            click.echo(f"Processing ServiceAccount: {sa}")

            # Create a token for the ServiceAccount with specified duration
            try:
                token = (
                    subprocess.check_output(
                        [
                            "kubectl",
                            "create",
                            "token",
                            sa,
                            "-n",
                            namespace,
                            f"--duration={token_duration}s",
                        ]
                    )
                    .decode("utf-8")
                    .strip()
                )
            except subprocess.CalledProcessError:
                click.echo(f"Failed to create token for ServiceAccount {sa}. Skipping...")
                continue

            # Create a kubeconfig file for the user
            kubeconfig_file = os.path.join(kubeconfig_dir, f"{sa}-{namespace}-kubeconfig")

            kubeconfig_content = f"""apiVersion: v1
kind: Config
clusters:
- name: {cluster_name}
  cluster:
    server: {cluster_server}
    certificate-authority-data: {cluster_ca}
users:
- name: {sa}
  user:
    token: {token}
contexts:
- name: {sa}-{namespace}
  context:
    cluster: {cluster_name}
    namespace: {namespace}
    user: {sa}
current-context: {sa}-{namespace}
"""
            with open(kubeconfig_file, "w") as f:
                f.write(kubeconfig_content)

            click.echo(f"Created kubeconfig file for {sa}: {kubeconfig_file}")
            click.echo(f"Token duration: {token_duration} seconds")
            click.echo(f"To use this config, run: kubectl --kubeconfig={kubeconfig_file} get pods")
            click.echo("---")

    click.echo(f"All kubeconfig files have been created in the '{kubeconfig_dir}' directory.")
    click.echo("Distribute these files to the respective users.")
    click.echo(
        "Users can then use them with kubectl by specifying the --kubeconfig flag or by setting the KUBECONFIG environment variable."
    )
    click.echo(f"Note: The tokens will expire after {token_duration} seconds.")
