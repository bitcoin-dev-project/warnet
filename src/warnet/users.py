import os
import sys

import click
import yaml

from warnet.constants import KUBECONFIG


@click.command()
@click.argument("auth_config", type=str)
def auth(auth_config):
    """Authenticate with a Warnet cluster using a kubernetes config file"""
    # TODO: use os.replace for more atomic file writing
    auth_config = yaml_try_with_open(auth_config)

    is_first_config = False
    if not os.path.exists(KUBECONFIG):
        with open(KUBECONFIG, "w") as file:
            yaml.safe_dump(auth_config, file)
            is_first_config = True

    base_config = yaml_try_with_open(KUBECONFIG)

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
        with open(KUBECONFIG, "w") as file:
            yaml.safe_dump(base_config, file)
            click.secho(f"Updated kubeconfig with authorization data: {KUBECONFIG}", fg="green")
    except OSError as e:
        click.secho(f"Error writing to {KUBECONFIG}: {e}", fg="red")
        sys.exit(1)

    try:
        with open(KUBECONFIG) as file:
            contents = yaml.safe_load(file)
            click.secho(
                f"Warnet's current context is now set to: {contents['current-context']}", fg="green"
            )
    except (OSError, yaml.YAMLError) as e:
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


def yaml_try_with_open(filename: str):
    try:
        with open(filename) as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        click.secho(f"Could not find: {KUBECONFIG}", fg="red")
        sys.exit(1)
    except OSError as e:
        click.secho(f"An I/O error occurred: {e}", fg="red")
        sys.exit(1)
    except Exception as e:
        click.secho(f"An unexpected error occurred: {e}", fg="red")
        sys.exit(1)
