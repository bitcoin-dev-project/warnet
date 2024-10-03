import os
from pathlib import Path

import click
from rich import print as richprint

from .constants import NETWORK_DIR, WARGAMES_NAMESPACE_PREFIX
from .k8s import get_kubeconfig_value, get_namespaces_by_prefix, get_service_accounts_in_namespace
from .namespaces import copy_namespaces_defaults, namespaces
from .network import copy_network_defaults
from .process import run_command


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
    """Create kubeconfig files for ServiceAccounts"""
    kubeconfig_dir = os.path.expanduser(kubeconfig_dir)

    cluster_name = get_kubeconfig_value("{.clusters[0].name}")
    cluster_server = get_kubeconfig_value("{.clusters[0].cluster.server}")
    cluster_ca = get_kubeconfig_value("{.clusters[0].cluster.certificate-authority-data}")

    os.makedirs(kubeconfig_dir, exist_ok=True)

    # Get all namespaces that start with prefix
    # This assumes when deploying multiple namespaces for the purpose of team games, all namespaces start with a prefix,
    # e.g., tabconf-wargames-*. Currently, this is a bit brittle, but we can improve on this in the future
    # by automatically applying a TEAM_PREFIX when creating the get_warnet_namespaces
    # TODO: choose a prefix convention and have it managed by the helm charts instead of requiring the
    # admin user to pipe through the correct string in multiple places. Another would be to use
    # labels instead of namespace naming conventions
    warnet_namespaces = get_namespaces_by_prefix(WARGAMES_NAMESPACE_PREFIX)

    for v1namespace in warnet_namespaces:
        namespace = v1namespace.metadata.name
        click.echo(f"Processing namespace: {namespace}")
        service_accounts = get_service_accounts_in_namespace(namespace)

        for sa in service_accounts:
            # Create a token for the ServiceAccount with specified duration
            command = f"kubectl create token {sa} -n {namespace} --duration={token_duration}s"
            try:
                token = run_command(command)
            except Exception as e:
                click.echo(
                    f"Failed to create token for ServiceAccount {sa} in namespace {namespace}. Error: {str(e)}. Skipping..."
                )
                continue

            # Create a kubeconfig file for the user
            kubeconfig_file = os.path.join(kubeconfig_dir, f"{sa}-{namespace}-kubeconfig")

            # TODO: move yaml  out of python code to resources/manifests/
            #
            # might not be worth it since we are just reading the yaml to then create a bunch of values and its not
            # actually used to deploy anything into the cluster
            # Then benefit would be making this code a bit cleaner and easy to follow, fwiw
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

            click.echo(f"    Created kubeconfig file for {sa}: {kubeconfig_file}")

    click.echo("---")
    click.echo(
        f"All kubeconfig files have been created in the '{kubeconfig_dir}' directory with a duration of {token_duration} seconds."
    )
    click.echo("Distribute these files to the respective users.")
    click.echo(
        "Users can then use by running `warnet auth <file>` or with kubectl by specifying the --kubeconfig flag or by setting the KUBECONFIG environment variable."
    )
    click.echo(f"Note: The tokens will expire after {token_duration} seconds.")
