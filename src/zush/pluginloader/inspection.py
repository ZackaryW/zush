from __future__ import annotations

from types import ModuleType


def find_plugin_instance(module: ModuleType) -> object | None:
    """Find an object in module that has a .commands dict. Prefer name ZushPlugin."""
    if hasattr(module, "ZushPlugin"):
        candidate = getattr(module, "ZushPlugin")
        if hasattr(candidate, "commands") and isinstance(getattr(candidate, "commands"), dict):
            return candidate
    for name in dir(module):
        if name.startswith("_"):
            continue
        candidate = getattr(module, name)
        if hasattr(candidate, "commands") and isinstance(getattr(candidate, "commands"), dict):
            return candidate
    return None
