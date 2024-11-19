import copy
import importlib.util
import inspect
import os
import sys
import tempfile
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Callable, Optional

import click
import inquirer
import yaml
from inquirer.themes import GreenPassion

from warnet.constants import (
    HOOK_NAME_KEY,
    HOOKS_API_FILE,
    HOOKS_API_STEM,
    PLUGINS_LABEL,
    WARNET_USER_DIR_ENV_VAR,
)


class PluginError(Exception):
    pass


hook_registry: set[Callable[..., Any]] = set()
imported_modules = {}


@click.group(name="plugin")
def plugin():
    """Control plugins"""
    pass


@plugin.command()
def ls():
    """List all available plugins and whether they are activated."""
    plugin_dir = get_plugin_directory()

    if not plugin_dir:
        click.secho("Could not determine the plugin directory location.")
        click.secho("Consider setting environment variable containing your project directory:")
        click.secho(f"export {WARNET_USER_DIR_ENV_VAR}=/home/user/path/to/project/", fg="yellow")
        sys.exit(1)

    for plugin, status in get_plugins_with_status(plugin_dir):
        if status:
            click.secho(f"{plugin.stem:<20} enabled", fg="green")
        else:
            click.secho(f"{plugin.stem:<20} disabled", fg="yellow")


@plugin.command()
@click.argument("plugin", type=str, default="")
def toggle(plugin: str):
    """Turn a plugin on or off"""
    plugin_dir = get_plugin_directory()

    if plugin == "":
        plugin_list = get_plugins_with_status(plugin_dir)
        formatted_list = [
            f"{str(name.stem):<25}| enabled: {active}" for name, active in plugin_list
        ]

        plugins_tag = "plugins"
        q = [
            inquirer.List(
                name=plugins_tag,
                message="Toggle a plugin, or ctrl-c to cancel",
                choices=formatted_list,
            )
        ]
        selected = inquirer.prompt(q, theme=GreenPassion())
        plugin = selected[plugins_tag].split("|")[0].strip()

    plugin_settings = read_yaml(plugin_dir / Path(plugin) / "plugin.yaml")
    updated_settings = copy.deepcopy(plugin_settings)
    updated_settings["enabled"] = not plugin_settings["enabled"]
    write_yaml(updated_settings, plugin_dir / Path(plugin) / Path("plugin.yaml"))


@plugin.command()
@click.argument("plugin", type=str)
@click.argument("function", type=str)
def run(plugin: str, function: str):
    module = imported_modules.get(f"plugins.{plugin}")
    if hasattr(module, function):
        func = getattr(module, function)
        if callable(func):
            result = func()
            print(result)
        else:
            click.secho(f"{function} in {module} is not callable.")
    else:
        click.secho(f"Could not find {function} in {module}")


def api(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    Functions with this decoration will have corresponding 'pre' and 'post' functions made
    available to the user via the 'plugins' directory.

    Please ensure that @api is the innermost decorator:

    ```python
    @click.command()  # outermost
    @api              # innermost
    def my_function():
        pass
    ```
    """
    if func.__name__ in [fn.__name__ for fn in hook_registry]:
        print(
            f"Cannot re-use function names in the Warnet plugin API -- "
            f"'{func.__name__}' has already been taken."
        )
        sys.exit(1)
    hook_registry.add(func)

    if not imported_modules:
        load_user_modules()

    pre_hooks, post_hooks = [], []
    for module_name in imported_modules:
        pre, post = find_hooks(module_name, func.__name__)
        pre_hooks.extend(pre)
        post_hooks.extend(post)

    def wrapped(*args, **kwargs):
        for hook in pre_hooks:
            hook()
        result = func(*args, **kwargs)
        for hook in post_hooks:
            hook()
        return result

    # Mimic the base function; helps make `click` happy
    wrapped.__name__ = func.__name__
    wrapped.__doc__ = func.__doc__

    return wrapped


def create_hooks(directory: Path):
    # Prepare directory and file
    os.makedirs(directory, exist_ok=True)
    init_file_path = os.path.join(directory, HOOKS_API_FILE)

    with open(init_file_path, "w") as file:
        file.write(f"# API Version: {get_version('warnet')}")
        # For each enum variant, create a corresponding decorator function
        for func in hook_registry:
            file.write(
                decorator_code.format(
                    hook=func.__name__, doc=func.__doc__, HOOK_NAME_KEY=HOOK_NAME_KEY
                )
            )

    click.secho("\nConsider setting environment variable containing your project directory:")
    click.secho(f"export {WARNET_USER_DIR_ENV_VAR}={directory.parent}\n", fg="yellow")


decorator_code = """


def pre_{hook}(func):
    \"\"\"
    Functions with this decoration run before `{hook}`.

    `{hook}` documentation:
    {doc}
    \"\"\"
    func.__annotations__['{HOOK_NAME_KEY}'] = 'pre_{hook}'
    return func


def post_{hook}(func):
    \"\"\"
    Functions with this decoration run after `{hook}`.

    `{hook}` documentation:
    {doc}
    \"\"\"
    func.__annotations__['{HOOK_NAME_KEY}'] = 'post_{hook}'
    return func
"""


def load_user_modules() -> bool:
    was_successful_load = False

    plugin_dir = get_plugin_directory()

    if not plugin_dir or not plugin_dir.is_dir():
        return was_successful_load

    enabled_plugins = [plugin for plugin, enabled in get_plugins_with_status(plugin_dir) if enabled]

    if not enabled_plugins:
        return was_successful_load

    # Temporarily add the directory to sys.path for imports
    sys.path.insert(0, str(plugin_dir))

    hooks_path = plugin_dir / HOOKS_API_FILE

    if hooks_path.is_file():
        hooks_spec = importlib.util.spec_from_file_location(HOOKS_API_STEM, hooks_path)
        hooks_module = importlib.util.module_from_spec(hooks_spec)
        imported_modules[HOOKS_API_STEM] = hooks_module
        sys.modules[HOOKS_API_STEM] = hooks_module
        hooks_spec.loader.exec_module(hooks_module)

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


def find_hooks(module_name: str, func_name: str):
    module = imported_modules.get(module_name)
    pre_hooks = []
    post_hooks = []
    for _, func in inspect.getmembers(module, inspect.isfunction):
        if func.__annotations__.get(HOOK_NAME_KEY) == f"pre_{func_name}":
            pre_hooks.append(func)
        elif func.__annotations__.get(HOOK_NAME_KEY) == f"post_{func_name}":
            post_hooks.append(func)
    return pre_hooks, post_hooks


def get_plugin_directory() -> Optional[Path]:
    user_dir = os.getenv(WARNET_USER_DIR_ENV_VAR)

    plugin_dir = Path(user_dir) / PLUGINS_LABEL if user_dir else Path.cwd() / PLUGINS_LABEL

    if plugin_dir and plugin_dir.is_dir():
        return plugin_dir
    else:
        return None


def get_version(package_name: str) -> str:
    try:
        return version(package_name)
    except PackageNotFoundError:
        print(f"Package not found: {package_name}")
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


def get_plugins_with_status(plugin_dir: Path) -> list[tuple[Path, bool]]:
    candidates = [
        Path(os.path.join(plugin_dir, name))
        for name in os.listdir(plugin_dir)
        if os.path.isdir(os.path.join(plugin_dir, name))
    ]
    plugins = [plugin_dir for plugin_dir in candidates if any(plugin_dir.glob("plugin.yaml"))]
    return [(plugin, check_if_plugin_enabled(plugin)) for plugin in plugins]
