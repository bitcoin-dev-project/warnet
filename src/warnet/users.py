import difflib
import json
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
        os.makedirs(os.path.dirname(KUBECONFIG), exist_ok=True)
        try:
            write_kubeconfig(auth_config, KUBECONFIG)
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
        for category in ["clusters", "users", "contexts"]:
            if category in auth_config:
                merge_entries(category, base_config, auth_config)

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
        write_kubeconfig(base_config, KUBECONFIG)
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


def merge_entries(category, base_config, auth_config):
    name = "name"
    base_list = base_config.setdefault(category, [])
    auth_list = auth_config[category]
    base_entry_names = {entry[name] for entry in base_list}  # Extract existing names
    for auth_entry in auth_list:
        if auth_entry[name] in base_entry_names:
            existing_entry = next(
                base_entry for base_entry in base_list if base_entry[name] == auth_entry[name]
            )
            if existing_entry != auth_entry:
                # Show diff between existing and new entry
                existing_entry_str = json.dumps(existing_entry, indent=2, sort_keys=True)
                auth_entry_str = json.dumps(auth_entry, indent=2, sort_keys=True)
                diff = difflib.unified_diff(
                    existing_entry_str.splitlines(),
                    auth_entry_str.splitlines(),
                    fromfile="Existing Entry",
                    tofile="New Entry",
                    lineterm="",
                )
                click.echo("Differences between existing and new entry:\n")
                click.echo("\n".join(diff))

                if click.confirm(
                    f"The '{category}' section key '{auth_entry[name]}' already exists and differs. Overwrite?",
                    default=False,
                ):
                    # Find and replace the existing entry
                    base_list[:] = [
                        base_entry if base_entry[name] != auth_entry[name] else auth_entry
                        for base_entry in base_list
                    ]
                    click.secho(
                        f"Overwrote '{category}' section key '{auth_entry[name]}'", fg="yellow"
                    )
                else:
                    click.secho(
                        f"Skipped '{category}' section key '{auth_entry[name]}'", fg="yellow"
                    )
            else:
                click.secho(
                    f"Entry for '{category}' section key '{auth_entry[name]}' is identical. No changes made.",
                    fg="blue",
                )
        else:
            base_list.append(auth_entry)
            click.secho(f"Added new '{category}' section key '{auth_entry[name]}'", fg="green")
