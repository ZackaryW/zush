from __future__ import annotations

from types import ModuleType


def find_plugin_instance(module: ModuleType) -> object | None:
    """Find an object in module that has a .commands dict. Prefer name ZushPlugin."""
    if hasattr(module, "ZushPlugin"):
        obj = getattr(module, "ZushPlugin")
        if hasattr(obj, "commands") and isinstance(getattr(obj, "commands"), dict):
            return obj
    for name in dir(module):
        if name.startswith("_"):
            continue
        obj = getattr(module, name)
        if hasattr(obj, "commands") and isinstance(getattr(obj, "commands"), dict):
            return obj
    return None
