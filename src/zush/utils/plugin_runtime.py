from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from zush.context import HookRegistry, ZushCtx

if TYPE_CHECKING:
    from zush.paths import ZushStorage


def register_plugin_hooks(
    plugins: list[tuple[Any, Any, Any]],
    hook_registry: HookRegistry,
    zush_ctx: ZushCtx,
) -> None:
    for _path, instance, _commands in plugins:
        before = getattr(instance, "before_cmd", None)
        if before and isinstance(before, list):
            for pattern, callback in before:
                if isinstance(pattern, str):
                    pattern = re.compile(pattern)
                hook_registry.register_before_cmd(pattern, callback)
        after = getattr(instance, "after_cmd", None)
        if after and isinstance(after, list):
            for pattern, callback in after:
                if isinstance(pattern, str):
                    pattern = re.compile(pattern)
                hook_registry.register_after_cmd(pattern, callback)
        on_error = getattr(instance, "on_error", None)
        if on_error and isinstance(on_error, list):
            for exc_type, callback in on_error:
                hook_registry.register_on_error(exc_type, callback)
        on_ctx_match = getattr(instance, "on_ctx_match", None)
        if on_ctx_match and isinstance(on_ctx_match, list):
            for key, value, callback in on_ctx_match:
                zush_ctx.register_on_ctx_match(key, value, callback)


def bind_plugin_runtime(plugins: list[tuple[Any, Any, Any]], storage: ZushStorage) -> None:
    for path, instance, _commands in plugins:
        bind = getattr(instance, "_bind_runtime", None)
        if callable(bind):
            bind(path.name, storage)
