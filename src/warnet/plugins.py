import copy
import importlib.util
import inspect
import os
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Optional

import click
import inquirer
import yaml
from inquirer.themes import GreenPassion

from warnet.constants import (
    CONTAINER_TAG,
    ENABLED_TAG,
    MISSION_TAG,
    PLUGIN_YAML,
    PLUGINS_TAG,
    USER_DIR_TAG,
    WARNET_USER_DIR_ENV_VAR,
)


class PluginError(Exception):
    pass


imported_modules: dict[str, ModuleType] = {}


@click.group(name=PLUGINS_TAG)
def plugins():
    """Control plugins"""
    pass


@plugins.command()
@click.pass_context
def ls(ctx):
    """List all available plugins and whether they are activated"""
    plugin_dir = get_plugins_directory_or(ctx.obj.get(USER_DIR_TAG))
    if plugin_dir is None:
        direct_user_to_plugin_directory_and_exit()

    for plugin, status in get_plugins_with_status(plugin_dir):
        if status:
            click.secho(f"{plugin.stem:<20} enabled", fg="green")
        else:
            click.secho(f"{plugin.stem:<20} disabled", fg="yellow")


@plugins.command()
@click.argument("plugin", type=str, default="")
@click.pass_context
def toggle(ctx, plugin: str):
    """Toggle a plugin on or off"""
    plugin_dir = get_plugins_directory_or(ctx.obj.get(USER_DIR_TAG))
    if plugin_dir is None:
        direct_user_to_plugin_directory_and_exit()

    if plugin == "":
        plugin_list = get_plugins_with_status(plugin_dir)
        formatted_list = [
            f"{str(name.stem):<25} ◦ enabled: {active}" for name, active in plugin_list
        ]

        try:
            q = [
                inquirer.List(
                    name=PLUGINS_TAG,
                    message="Toggle a plugin, or ctrl-c to cancel",
                    choices=formatted_list,
                )
            ]
            selected = inquirer.prompt(q, theme=GreenPassion())
            plugin = selected[PLUGINS_TAG].split("◦")[0].strip()
        except TypeError:
            # user cancels and `selected[plugins_tag] fails with TypeError
            sys.exit(0)

    plugin_settings = read_yaml(plugin_dir / Path(plugin) / PLUGIN_YAML)
    updated_settings = copy.deepcopy(plugin_settings)
    updated_settings[ENABLED_TAG] = not plugin_settings[ENABLED_TAG]
    write_yaml(updated_settings, plugin_dir / Path(plugin) / Path(PLUGIN_YAML))


def load_user_modules(path: Optional[Path] = None) -> bool:
    was_successful_load = False

    plugin_dir = get_plugins_directory_or(path)

    if not plugin_dir or not plugin_dir.is_dir():
        return was_successful_load

    enabled_plugins = [plugin for plugin, enabled in get_plugins_with_status(plugin_dir) if enabled]

    if not enabled_plugins:
        return was_successful_load

    # Temporarily add the directory to sys.path for imports
    sys.path.insert(0, str(plugin_dir))

    for plugin_path in enabled_plugins:
        for file in plugin_path.glob("*.py"):
            if file.stem not in ("__init__"):
                module_name = f"{PLUGINS_TAG}.{file.stem}"
                spec = importlib.util.spec_from_file_location(module_name, file)
                module = importlib.util.module_from_spec(spec)
                imported_modules[module_name] = module
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
                was_successful_load = True

    # Remove the added path from sys.path
    sys.path.pop(0)
    return was_successful_load


def register_command(command):
    """Register a command to the CLI."""
    from warnet.main import cli

    register = cli.commands.get(PLUGINS_TAG)
    register.add_command(command)


def load_plugins():
    for module in imported_modules.values():
        for name, func in inspect.getmembers(module, inspect.isfunction):
            if name == "warnet_register_plugin":
                func(register_command)


def get_plugins_directory_or(path: Optional[Path] = None) -> Optional[Path]:
    """Get the plugins directory
    user-provided path > environment variable > relative path
    """
    if path:
        if path.is_dir():
            return path / PLUGINS_TAG
        else:
            click.secho(f"Not a directory: {path}", fg="red")

    user_dir = os.getenv(WARNET_USER_DIR_ENV_VAR)

    plugin_dir = Path(user_dir) / PLUGINS_TAG if user_dir else Path.cwd() / PLUGINS_TAG

    if plugin_dir and plugin_dir.is_dir():
        return plugin_dir
    else:
        return None


def direct_user_to_plugin_directory_and_exit():
    click.secho("Could not determine the plugin directory location.")
    click.secho(
        "Solution 1: try runing this command again, but this time from your initialized Warnet directory."
    )
    click.secho(
        "Solution 2: consider setting environment variable pointing to your Warnet project directory:"
    )
    click.secho(f"export {WARNET_USER_DIR_ENV_VAR}=/home/user/path/to/project/", fg="yellow")
    sys.exit(1)


def read_yaml(path: Path) -> dict:
    try:
        with open(path) as file:
            return yaml.safe_load(file)
    except FileNotFoundError as e:
        raise PluginError(f"YAML file {path} not found.") from e
    except yaml.YAMLError as e:
        raise PluginError(f"Error parsing yaml: {e}") from e


def write_yaml(yaml_dict: dict, path: Path) -> None:
    dir_name = os.path.dirname(path)
    try:
        with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False) as temp_file:
            yaml.safe_dump(yaml_dict, temp_file)
        os.replace(temp_file.name, path)
    except Exception as e:
        os.remove(temp_file.name)
        raise PluginError(f"Error writing kubeconfig: {path}") from e


def check_if_plugin_enabled(path: Path) -> bool:
    enabled = None
    try:
        plugin_dict = read_yaml(path / Path(PLUGIN_YAML))
        enabled = plugin_dict.get(ENABLED_TAG)
    except PluginError as e:
        click.secho(e)

    return bool(enabled)


def get_plugins_with_status(plugin_dir: Optional[Path] = None) -> list[tuple[Path, bool]]:
    if not plugin_dir:
        plugin_dir = get_plugins_directory_or()
    candidates = [
        Path(os.path.join(plugin_dir, name))
        for name in os.listdir(plugin_dir)
        if os.path.isdir(os.path.join(plugin_dir, name))
    ]
    plugins = [plugin_dir for plugin_dir in candidates if any(plugin_dir.glob(PLUGIN_YAML))]
    return [(plugin, check_if_plugin_enabled(plugin)) for plugin in plugins]


def get_plugin_missions() -> list[str]:
    return [getattr(module, MISSION_TAG.upper(), None) for module in imported_modules.values()]


def get_plugin_primary_containers() -> list[str]:
    return [getattr(module, CONTAINER_TAG.upper(), None) for module in imported_modules.values()]
