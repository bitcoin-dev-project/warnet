import copy
import importlib.util
import inspect
import os
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Optional

import click
import inquirer
import yaml
from inquirer.themes import GreenPassion

from warnet.constants import (
    HOOKS_API_STEM,
    PLUGINS_LABEL,
    WARNET_USER_DIR_ENV_VAR,
)


class PluginError(Exception):
    pass


hook_registry: set[Callable[..., Any]] = set()
imported_modules: dict[str, ModuleType] = {}


@click.group(name="plugin")
def plugin():
    """Control plugins"""
    pass


@plugin.command()
def ls():
    """List all available plugins and whether they are activated"""
    plugin_dir = _get_plugin_directory()
    if plugin_dir is None:
        direct_user_to_plugin_directory_and_exit()

    for plugin, status in get_plugins_with_status(plugin_dir):
        if status:
            click.secho(f"{plugin.stem:<20} enabled", fg="green")
        else:
            click.secho(f"{plugin.stem:<20} disabled", fg="yellow")


@plugin.command()
@click.argument("plugin", type=str, default="")
def toggle(plugin: str):
    """Toggle a plugin on or off"""
    plugin_dir = _get_plugin_directory()
    if plugin_dir is None:
        direct_user_to_plugin_directory_and_exit()

    if plugin == "":
        plugin_list = get_plugins_with_status(plugin_dir)
        formatted_list = [
            f"{str(name.stem):<25}| enabled: {active}" for name, active in plugin_list
        ]

        plugins_tag = "plugins"
        try:
            q = [
                inquirer.List(
                    name=plugins_tag,
                    message="Toggle a plugin, or ctrl-c to cancel",
                    choices=formatted_list,
                )
            ]
            selected = inquirer.prompt(q, theme=GreenPassion())
            plugin = selected[plugins_tag].split("|")[0].strip()
        except TypeError:
            # user cancels and `selected[plugins_tag] fails with TypeError
            sys.exit(0)

    plugin_settings = read_yaml(plugin_dir / Path(plugin) / "plugin.yaml")
    updated_settings = copy.deepcopy(plugin_settings)
    updated_settings["enabled"] = not plugin_settings["enabled"]
    write_yaml(updated_settings, plugin_dir / Path(plugin) / Path("plugin.yaml"))


def load_user_modules() -> bool:
    was_successful_load = False

    plugin_dir = _get_plugin_directory()

    if not plugin_dir or not plugin_dir.is_dir():
        return was_successful_load

    enabled_plugins = [plugin for plugin, enabled in get_plugins_with_status(plugin_dir) if enabled]

    if not enabled_plugins:
        return was_successful_load

    # Temporarily add the directory to sys.path for imports
    sys.path.insert(0, str(plugin_dir))

    for plugin_path in enabled_plugins:
        for file in plugin_path.glob("*.py"):
            if file.stem not in ("__init__", HOOKS_API_STEM):
                module_name = f"{PLUGINS_LABEL}.{file.stem}"
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

    register = cli.commands.get("register")
    register.add_command(command)


def load_plugins(fn):
    load_user_modules()
    for module in imported_modules.values():
        for name, func in inspect.getmembers(module, inspect.isfunction):
            if name == "_register":
                func(register_command)


def _get_plugin_directory() -> Optional[Path]:
    user_dir = os.getenv(WARNET_USER_DIR_ENV_VAR)

    plugin_dir = Path(user_dir) / PLUGINS_LABEL if user_dir else Path.cwd() / PLUGINS_LABEL

    if plugin_dir and plugin_dir.is_dir():
        return plugin_dir
    else:
        return None


def direct_user_to_plugin_directory_and_exit():
    click.secho("Could not determine the plugin directory location.")
    click.secho(
        "Solution 1: try runing this command again, but this time from your initialized warnet directory."
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
        plugin_dict = read_yaml(path / Path("plugin.yaml"))
        enabled = plugin_dict.get("enabled")
    except PluginError as e:
        click.secho(e)

    return bool(enabled)


def get_plugins_with_status(plugin_dir: Optional[Path] = None) -> list[tuple[Path, bool]]:
    if not plugin_dir:
        plugin_dir = _get_plugin_directory()
    candidates = [
        Path(os.path.join(plugin_dir, name))
        for name in os.listdir(plugin_dir)
        if os.path.isdir(os.path.join(plugin_dir, name))
    ]
    plugins = [plugin_dir for plugin_dir in candidates if any(plugin_dir.glob("plugin.yaml"))]
    return [(plugin, check_if_plugin_enabled(plugin)) for plugin in plugins]
