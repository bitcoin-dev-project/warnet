import importlib.util
import inspect
import os
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Callable

from warnet.constants import HOOK_NAME_KEY, HOOKS_API_FILE, HOOKS_API_STEM

hook_registry: set[str] = set()
imported_modules = {}


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
    if func.__name__ in hook_registry:
        print(
            f"Cannot re-use function names in the Warnet plugin API -- "
            f"'{func.__name__}' has already been taken."
        )
        sys.exit(1)
    hook_registry.add(func.__name__)

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
        for hook in hook_registry:
            file.write(decorator_code.format(hook=hook, HOOK_NAME_KEY=HOOK_NAME_KEY))


decorator_code = """


def pre_{hook}(func):
    \"\"\"Functions with this decoration run before `{hook}`.\"\"\"
    func.__annotations__['{HOOK_NAME_KEY}'] = 'pre_{hook}'
    return func


def post_{hook}(func):
    \"\"\"Functions with this decoration run after `{hook}`.\"\"\"
    func.__annotations__['{HOOK_NAME_KEY}'] = 'post_{hook}'
    return func
"""


def load_user_modules() -> bool:
    was_successful_load = False
    user_module_path = Path.cwd() / "plugins"

    if not user_module_path.is_dir():
        return was_successful_load

    # Temporarily add the current directory to sys.path for imports
    sys.path.insert(0, str(Path.cwd()))

    hooks_path = user_module_path / HOOKS_API_FILE
    if hooks_path.is_file():
        hooks_spec = importlib.util.spec_from_file_location(HOOKS_API_STEM, hooks_path)
        hooks_module = importlib.util.module_from_spec(hooks_spec)
        imported_modules[HOOKS_API_STEM] = hooks_module
        sys.modules[HOOKS_API_STEM] = hooks_module
        hooks_spec.loader.exec_module(hooks_module)

    for file in user_module_path.glob("*.py"):
        if file.stem not in ("__init__", HOOKS_API_STEM):
            module_name = f"plugins.{file.stem}"
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


def get_version(package_name: str) -> str:
    try:
        return version(package_name)
    except PackageNotFoundError:
        print(f"Package not found: {package_name}")
        sys.exit(1)
