import os
import sys

import click

from warnet.constants import KUBECONFIG
from warnet.k8s import K8sError, open_kubeconfig, write_kubeconfig


@click.command()
@click.argument("auth_config", type=str)
def auth(auth_config):
    """Authenticate with a Warnet cluster using a kubernetes config file"""
    try:
        auth_config = open_kubeconfig(auth_config)
    except K8sError as e:
        click.secho(e, fg="yellow")
        click.secho(f"Could not open auth_config: {auth_config}", fg="red")
        sys.exit(1)

    is_first_config = False
    if not os.path.exists(KUBECONFIG):
        try:
            write_kubeconfig(auth_config)
            is_first_config = True
        except K8sError as e:
            click.secho(e, fg="yellow")
            click.secho(f"Could not write KUBECONFIG: {KUBECONFIG}", fg="red")
            sys.exit(1)

    try:
        base_config = open_kubeconfig(KUBECONFIG)
    except K8sError as e:
        click.secho(e, fg="yellow")
        click.secho(f"Could not open KUBECONFIG: {KUBECONFIG}", fg="red")
        sys.exit(1)

    if not is_first_config:
        clusters = "clusters"
        if clusters in auth_config:
            merge_entries(
                base_config.setdefault(clusters, []), auth_config[clusters], "name", "cluster"
            )

        users = "users"
        if users in auth_config:
            merge_entries(base_config.setdefault(users, []), auth_config[users], "name", "user")

        contexts = "contexts"
        if contexts in auth_config:
            merge_entries(
                base_config.setdefault(contexts, []), auth_config[contexts], "name", "context"
            )

    new_current_context = auth_config.get("current-context")
    base_config["current-context"] = new_current_context

    # Check if the new current context has an explicit namespace
    context_entry = next(
        (ctx for ctx in base_config["contexts"] if ctx["name"] == new_current_context), None
    )
    if context_entry and "namespace" not in context_entry["context"]:
        click.secho(
            f"Warning: The context '{new_current_context}' does not have an explicit namespace.",
            fg="yellow",
        )

    try:
        write_kubeconfig(base_config)
        click.secho(f"Updated kubeconfig with authorization data: {KUBECONFIG}", fg="green")
    except K8sError as e:
        click.secho(e, fg="yellow")
        click.secho(f"Could not write KUBECONFIG: {KUBECONFIG}", fg="red")
        sys.exit(1)

    try:
        base_config = open_kubeconfig(KUBECONFIG)
        click.secho(
            f"Warnet's current context is now set to: {base_config['current-context']}", fg="green"
        )
    except K8sError as e:
        click.secho(f"Error reading from {KUBECONFIG}: {e}", fg="red")
        sys.exit(1)


def merge_entries(base_list, auth_list, key, entry_type):
    base_entry_names = {entry[key] for entry in base_list}  # Extract existing names
    for entry in auth_list:
        if entry[key] in base_entry_names:
            if click.confirm(
                f"The {entry_type} '{entry[key]}' already exists. Overwrite?", default=False
            ):
                # Find and replace the existing entry
                base_list[:] = [e if e[key] != entry[key] else entry for e in base_list]
                click.secho(f"Overwrote {entry_type} '{entry[key]}'", fg="yellow")
            else:
                click.secho(f"Skipped {entry_type} '{entry[key]}'", fg="yellow")
        else:
            base_list.append(entry)
            click.secho(f"Added new {entry_type} '{entry[key]}'", fg="green")
