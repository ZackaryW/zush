"""Zush CLI entry point."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from zush.config import Config, load_config
from zush.context import ZushCtx, HookRegistry
from zush.discovery import run_discovery
from zush.group import ZushGroup, add_reserved_self_group, merge_commands_into_group
from zush.paths import default_storage
from zush.utils.cli import (
    parse_mock_path as _parse_mock_path,
)
from zush.utils.plugin_runtime import (
    bind_plugin_runtime as _bind_plugin_runtime,
    register_plugin_hooks as _register_plugin_hooks,
)

if TYPE_CHECKING:
    from zush.paths import ZushStorage


def create_zush_group(
    name: str = "zush",
    config: Config | None = None,
    storage: ZushStorage | None = None,
    mock_path: Path | None = None,
) -> ZushGroup:
    """Build and return a Click Group for zush. Use as standalone CLI or mount under another app.
    When config is None, load from storage (or default paths). When storage is None, use default (~/.zush).
    """
    storage = storage or default_storage()
    config = config or load_config(storage=storage)
    if mock_path is None:
        storage.config_dir().mkdir(parents=True, exist_ok=True)
    plugins, _tree = run_discovery(
        config,
        mock_path=mock_path,
        no_cache=mock_path is not None,
        storage=storage,
    )
    _bind_plugin_runtime(plugins, storage)
    zush_ctx = ZushCtx()
    hook_registry = HookRegistry()
    _register_plugin_hooks(plugins, hook_registry, zush_ctx)
    cli = ZushGroup(name, zush_ctx=zush_ctx, hook_registry=hook_registry)
    merge_commands_into_group(cli, plugins)
    add_reserved_self_group(cli, storage=storage)
    return cli


def main() -> None:
    """Entry point: parse argv, build group via create_zush_group, invoke."""
    argv = list(sys.argv[1:])
    mock_path, argv = _parse_mock_path(argv)
    cli = create_zush_group(mock_path=mock_path)
    sys.argv = [sys.argv[0], *argv]
    cli.main()
