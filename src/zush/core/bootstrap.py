"""Zush CLI bootstrap and root group factory."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click

from zush.configparse.config import Config, load_config
from zush.core.context import HookRegistry, ZushCtx
from zush.core.discovery import run_discovery
from zush.core.group import ZushGroup, add_reserved_self_group, merge_commands_into_group
from zush.core.runtime import g
from zush.core.services import ServiceController, collect_plugin_services
from zush.core.storage import default_storage
from zush.discovery_provider import DiscoveryDiagnostic
from zush.mocking.cli import parse_mock_path as _parse_mock_path
from zush.pluginloader.runtime import (
    bind_plugin_runtime_with_services as _bind_plugin_runtime,
    register_plugin_globals as _register_plugin_globals,
    register_plugin_hooks as _register_plugin_hooks,
)
from zush.utils.discovery import resolve_extension_key

if TYPE_CHECKING:
    from zush.core.storage import ZushStorage


def create_zush_group(
    name: str = "zush",
    config: Config | None = None,
    storage: ZushStorage | None = None,
    mock_path: Path | None = None,
    system_commands: dict[str, click.Command | click.Group] | None = None,
) -> ZushGroup:
    """Build and return a Click Group for zush."""
    storage = storage or default_storage()
    config = config or load_config(storage=storage)
    if mock_path is None:
        storage.config_dir().mkdir(parents=True, exist_ok=True)
    diagnostics: list[DiscoveryDiagnostic] = []
    plugins, _tree = run_discovery(
        config,
        mock_path=mock_path,
        no_cache=mock_path is not None,
        storage=storage,
        diagnostics=diagnostics,
    )
    g.clear()
    service_controller = ServiceController(storage, collect_plugin_services(plugins))
    _bind_plugin_runtime(plugins, storage, service_controller)
    _register_plugin_globals(plugins)
    zush_ctx = ZushCtx()
    hook_registry = HookRegistry()
    _register_plugin_hooks(plugins, hook_registry, zush_ctx)
    cli = ZushGroup(name, zush_ctx=zush_ctx, hook_registry=hook_registry)
    merge_commands_into_group(cli, plugins, diagnostics=diagnostics)
    add_reserved_self_group(
        cli,
        storage=storage,
        service_controller=service_controller,
        loaded_extensions=sorted({resolve_extension_key(path) for path, _instance, _commands in plugins}),
        system_commands=_merge_system_commands(system_commands or {}, _collect_plugin_system_commands(plugins)),
        diagnostics=diagnostics,
    )
    return cli


def _collect_plugin_system_commands(
    plugins: list[tuple[Path, object, dict[str, object]]],
) -> dict[str, object]:
    """Collect plugin-owned self commands from loaded plugin instances in discovery order."""
    collected: dict[str, object] = {}
    for _path, instance, _commands in plugins:
        plugin_system_commands = getattr(instance, "system_commands", None)
        if not isinstance(plugin_system_commands, dict):
            continue
        for name, command in plugin_system_commands.items():
            if isinstance(name, str) and name and name not in collected:
                collected[name] = command
    return collected


def _merge_system_commands(
    host_system_commands: dict[str, object],
    plugin_system_commands: dict[str, object],
) -> dict[str, object]:
    """Merge host and plugin self commands with host precedence over plugins."""
    merged = dict(host_system_commands)
    for name, command in plugin_system_commands.items():
        if name not in merged:
            merged[name] = command
    return merged


def main() -> None:
    """Entry point: parse argv, build group via create_zush_group, invoke."""
    argv = list(sys.argv[1:])
    mock_path, argv = _parse_mock_path(argv)
    cli = create_zush_group(mock_path=mock_path)
    sys.argv = [sys.argv[0], *argv]
    cli.main()
