"""Zush CLI entry point."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from zush.config import load_config
from zush.context import ZushCtx, HookRegistry
from zush.discovery import run_discovery
from zush.group import ZushGroup, add_reserved_self_group, merge_commands_into_group
from zush.paths import config_dir


def main() -> None:
    """Entry point: load config, discover plugins, build group, invoke."""
    argv = list(sys.argv[1:])
    mock_path, argv = _parse_mock_path(argv)

    config_dir().mkdir(parents=True, exist_ok=True)
    config = load_config()
    plugins, _tree = run_discovery(
        config,
        mock_path=mock_path,
        no_cache=mock_path is not None,
    )

    zush_ctx = ZushCtx()
    hook_registry = HookRegistry()
    _register_plugin_hooks(plugins, hook_registry, zush_ctx)
    cli = ZushGroup("zush", zush_ctx=zush_ctx, hook_registry=hook_registry)
    merge_commands_into_group(cli, plugins)
    add_reserved_self_group(cli)
    sys.argv = [sys.argv[0], *argv]
    cli.main()


def _parse_mock_path(argv: list[str]) -> tuple[Path | None, list[str]]:
    """Strip --mock-path / -m and its value from argv. Return (path or None, remaining argv)."""
    out: list[str] = []
    mock_path: Path | None = None
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("--mock-path", "-m"):
            if i + 1 < len(argv):
                mock_path = Path(argv[i + 1])
                i += 2
                continue
        out.append(arg)
        i += 1
    return mock_path, out


def _register_plugin_hooks(
    plugins: list[tuple],
    hook_registry: HookRegistry,
    zush_ctx: ZushCtx,
) -> None:
    """Infer hooks from plugin instances (before_cmd, after_cmd, on_error, on_ctx_match)."""
    for _path, instance, _commands in plugins:
        before = getattr(instance, "before_cmd", None)
        if before and isinstance(before, list):
            for pattern, cb in before:
                if isinstance(pattern, str):
                    pattern = re.compile(pattern)
                hook_registry.register_before_cmd(pattern, cb)
        after = getattr(instance, "after_cmd", None)
        if after and isinstance(after, list):
            for pattern, cb in after:
                if isinstance(pattern, str):
                    pattern = re.compile(pattern)
                hook_registry.register_after_cmd(pattern, cb)
        on_err = getattr(instance, "on_error", None)
        if on_err and isinstance(on_err, list):
            for exc_type, cb in on_err:
                hook_registry.register_on_error(exc_type, cb)
        on_ctx = getattr(instance, "on_ctx_match", None)
        if on_ctx and isinstance(on_ctx, list):
            for key, value, cb in on_ctx:
                zush_ctx.register_on_ctx_match(key, value, cb)
