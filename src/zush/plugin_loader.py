"""Load __zush__.py from a package path; return plugin instance and commands dict."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from zush.utils.plugin_loader import find_plugin_instance as _find_plugin_instance


def load_plugin(package_path: Path) -> tuple[object, dict[str, object]]:
    """Load __zush__.py from package_path. Returns (instance, commands_dict).
    Raises FileNotFoundError if __zush__.py is missing; ValueError if no plugin found.
    """
    module_path = package_path / "__zush__.py"
    if not module_path.exists():
        raise FileNotFoundError(f"No __zush__.py in {package_path}")

    spec = importlib.util.spec_from_file_location("__zush__", module_path, submodule_search_locations=[str(package_path)])
    if spec is None or spec.loader is None:
        raise ValueError(f"Cannot load __zush__.py from {package_path}")

    module = importlib.util.module_from_spec(spec)
    # Load without registering in sys.modules to avoid clashes when loading multiple plugins
    spec.loader.exec_module(module)

    instance = _find_plugin_instance(module)
    if instance is None:
        raise ValueError(f"No plugin instance with .commands in {module_path}")
    commands = getattr(instance, "commands", None)
    if not isinstance(commands, dict):
        raise ValueError(f"Plugin instance has no .commands dict in {module_path}")
    return instance, dict(commands)
