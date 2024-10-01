import click

from .constants import (
    WARGAMES_NAMESPACE_PREFIX,
)
from .k8s import get_static_client


@click.group(name="service-accounts")
def service_accounts():
    """Service account commands"""


@service_accounts.command()
def list():
    """List all service accounts with 'wargames-' prefix"""
    # Load the kubeconfig file
    sclient = get_static_client()
    namespaces = sclient.list_namespace().items

    filtered_namespaces = [
        ns.metadata.name
        for ns in namespaces
        if ns.metadata.name.startswith(WARGAMES_NAMESPACE_PREFIX)
    ]

    if len(filtered_namespaces) == 0:
        click.secho("Could not find any matching service accounts.", fg="yellow")

    for namespace in filtered_namespaces:
        click.secho(f"Service accounts in namespace: {namespace}")
        service_accounts = sclient.list_namespaced_service_account(namespace=namespace).items

        if len(service_accounts) == 0:
            click.secho("...Could not find any matching service accounts", fg="yellow")

        for sa in service_accounts:
            click.secho(f"- {sa.metadata.name}", fg="green")
