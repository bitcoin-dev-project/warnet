import copy
import importlib.util
import inspect
import json
import os
import sys
import tempfile
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Optional, Union, get_args, get_origin, get_type_hints

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


@plugin.command()
@click.argument("plugin_name", type=str, default="")
@click.argument("function_name", type=str, default="")
@click.option(
    "--params", type=str, default="", help="Parameter data to be fed to the plugin function"
)
def run(plugin_name: str, function_name: str, params: str):
    """Explore and run plugins

    Use `--params` to pass a JSON list for positional arguments or a JSON object for named arguments.

    Like this:

    Positional - '["first element", 2, 3.0]'

    Named      - '{"first": "first_element", "second": 2, "third": 3.0}'
    """
    show_explainer = False

    plugin_dir = _get_plugin_directory()
    if plugin_dir is None:
        direct_user_to_plugin_directory_and_exit()

    plugins = get_plugins_with_status(plugin_dir)
    plugin_was_found = False
    for plugin_path, status in plugins:
        if plugin_path.stem == plugin_name:
            plugin_was_found = True
        if plugin_path.stem == plugin_name and not status:
            click.secho(f"The plugin '{plugin_path.stem}' is not enabled", fg="yellow")
            click.secho("Please toggle it on to use it.")
            sys.exit(0)
    if plugin_name and not plugin_was_found:
        click.secho(f"The plugin '{plugin_name}' was not found.", fg="yellow")
        sys.exit(0)

    if plugin_name == "":
        show_explainer = True
        plugin_names = [
            plugin_name.stem for plugin_name, status in get_plugins_with_status() if status
        ]
        q = [inquirer.List(name="plugin", message="Please choose a plugin", choices=plugin_names)]

        plugin_answer = inquirer.prompt(q, theme=GreenPassion())
        if not plugin_answer:
            sys.exit(0)
        plugin_name = plugin_answer.get("plugin")

    if function_name == "":
        show_explainer = True
        module = imported_modules.get(f"plugins.{plugin_name}")
        funcs = [
            format_func_with_docstring(func)
            for _name, func in inspect.getmembers(module, inspect.isfunction)
            if func.__module__ == "plugins." + plugin_name and not func.__name__.startswith("_")
        ]
        q = [inquirer.List(name="func", message="Please choose a function", choices=funcs)]
        function_answer = inquirer.prompt(q, theme=GreenPassion())
        if not function_answer:
            sys.exit(0)
        function_name_with_doc = function_answer.get("func")
        function_name = function_name_with_doc.split("\t")[0].strip()

    func = get_func(function_name=function_name, plugin_name=plugin_name)
    hints = get_type_hints(func)
    if not func:
        sys.exit(0)

    if not params:
        params = {}
        sig = inspect.signature(func)
        for name, param in sig.parameters.items():
            hint = hints.get(name)
            hint_name = get_type_name(hint)
            if param.default != inspect.Parameter.empty:
                q = [
                    inquirer.Text(
                        "input",
                        message=f"Enter a value for '{name}' ({hint_name})",
                        default=param.default,
                    )
                ]
            else:
                q = [
                    inquirer.Text(
                        "input",
                        message=f"Enter a value for '{name}' ({hint_name})",
                    )
                ]
            user_input_answer = inquirer.prompt(q)
            if not user_input_answer:
                sys.exit(0)
            user_input = user_input_answer.get("input")

            if hint is None:
                params[name] = user_input
            else:
                params[name] = cast_to_hint(user_input, hint)

        if show_explainer:
            if not params:
                click.secho(
                    f"\nwarnet plugin run {plugin_name} {function_name}\n",
                    fg="green",
                )
            else:
                click.secho(
                    f"\nwarnet plugin run {plugin_name} {function_name} --params '{json.dumps(params)}'",
                    fg="green",
                )
    else:
        params = json.loads(params)

    execute_function_with_params(func, params)


def execute_function_with_params(func: Callable[..., Any], params: dict | list):
    try:
        if isinstance(params, dict):
            return_value = func(**params)
        elif isinstance(params, list):
            return_value = func(*params)
        else:
            click.secho(f"Did not anticipate this type: {params} --> {type(params)}", fg="red")
            sys.exit(1)

        if return_value is not None:
            print(json.dumps(return_value))
    except Exception as e:
        click.secho(f"Exception: {e}", fg="yellow")
        sys.exit(1)


def process_obj(some_obj, func) -> dict:
    """
    Process a JSON-ish python obj into a param for the func

    Args:
        some_obj (JSON-ish): A python dict, list, str, int, float, or bool
        func (callable): A function object whose parameters are used for dictionary keys.

    Returns:
        dict: Params for the func
    """
    param_names = list(inspect.signature(func).parameters.keys())
    parameters = inspect.signature(func).parameters

    if isinstance(some_obj, dict):
        return some_obj
    elif isinstance(some_obj, list):
        if len(param_names) < len(some_obj):
            raise ValueError("Function parameters are fewer than the list items.")
        # If the function expects a single list parameter, use it directly
        if len(param_names) == 1:
            param_type = parameters[param_names[0]].annotation
            if get_origin(param_type) is list:
                return {param_names[0]: some_obj}
        # Otherwise, treat the list as a list of individual parameters
        return {key: value for key, value in zip(param_names, some_obj)}
    elif isinstance(some_obj, (str, int, float, bool)) or some_obj is None:
        if not param_names:
            raise ValueError("Function has no parameters to use as a key.")
        return {param_names[0]: some_obj}
    else:
        raise TypeError("Unsupported type.")


def cast_to_hint(value: str, hint: Any) -> Any:
    """
    Cast a string value to the provided type hint.
    """
    origin = get_origin(hint)
    args = get_args(hint)

    # Handle basic types (int, str, float, etc.)
    if origin is None:
        return hint(value)

    # Handle Union (e.g., Union[int, str])
    if origin is Union:
        for arg in args:
            try:
                return cast_to_hint(value, arg)
            except (ValueError, TypeError):
                continue
        raise ValueError(f"Cannot cast {value} to {hint}")

    # Handle Lists (e.g., List[int])
    if origin is list:
        return [cast_to_hint(v.strip(), args[0]) for v in value.split(",")]

    raise ValueError(f"Unsupported hint: {hint}")


def get_type_name(type_hint) -> str:
    if type_hint is None:
        return "Unknown type"
    if hasattr(type_hint, "__name__"):
        return type_hint.__name__
    return str(type_hint)


def get_func(function_name: str, plugin_name: str) -> Optional[Callable[..., Any]]:
    module = imported_modules.get(f"plugins.{plugin_name}")
    if hasattr(module, function_name):
        func = getattr(module, function_name)
        if callable(func):
            return func
        else:
            click.secho(f"{function_name} in {module} is not callable.")
    else:
        click.secho(f"Could not find {function_name} in {module}")
    return None


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

    click.secho("\nConsider setting an environment variable containing your project directory:")
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

    plugin_dir = _get_plugin_directory()

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


def format_func_with_docstring(func: Callable[..., Any]) -> str:
    name = func.__name__
    if func.__doc__:
        doc = func.__doc__.replace("\n", " ")
        doc = doc[:96]
        doc = click.style(doc, italic=True)
        return f"{name:<35}\t{doc}"
    else:
        return name
