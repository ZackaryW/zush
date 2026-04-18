"""Custom Click group with ZushCtx and hooks; merge plugin commands into group."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import click

from zush.configparse.config import load_config, toggle_extension
from zush.core.cron import add_cron_job, list_cron_jobs, remove_cron_job, start_cron_scheduler
from zush.core.context import HookRegistry, ZushCtx
from zush.core.services import ServiceController
from zush.core.storage import default_storage
from zush.discovery_provider import DiscoveryDiagnostic
from zush.utils.group import (
    command_path as _command_path,
    merge_commands_into_group as _merge_commands_into_group,
    print_command_tree as _print_command_tree,
)

RESERVED_GROUP_NAME = "self"


def merge_commands_into_group(
    group: click.Group,
    plugin_list: list[tuple[Any, Any, dict[str, click.Command | click.Group]]],
    diagnostics: list[DiscoveryDiagnostic] | None = None,
) -> None:
    """Backward-compatible wrapper for the shared group merge helper."""
    _merge_commands_into_group(group, plugin_list, diagnostics=diagnostics)


class ZushGroup(click.Group):
    """Click Group that holds ZushCtx, runs beforeCmd/afterCmd/onError, and sets ctx.obj."""

    def __init__(
        self,
        name: str | None = None,
        zush_ctx: ZushCtx | None = None,
        hook_registry: HookRegistry | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(name, **kwargs)
        self.zush_ctx = zush_ctx if zush_ctx is not None else ZushCtx()
        self.hook_registry = hook_registry or HookRegistry()

    def invoke(self, ctx: click.Context) -> Any:
        ctx.obj = self.zush_ctx
        command_path = _command_path(ctx)
        path_str = ".".join(command_path) if command_path else ""
        self.hook_registry.run_before_cmd(path_str)
        try:
            result = self._invoke_with_hooks(ctx)
            self.hook_registry.run_after_cmd(path_str)
            return result
        except BaseException as exc:
            self.hook_registry.run_on_error(exc)
            raise

    def _invoke_with_hooks(self, ctx: click.Context) -> Any:
        """Run the same logic as Group.invoke but set sub_ctx.obj so commands see ZushCtx."""
        protected = getattr(ctx, "_protected_args", []) or []
        if not protected and not ctx.args:
            if self.invoke_without_command:
                return super().invoke(ctx)
            return ctx.fail("Missing command.")
        args = [*protected, *ctx.args]
        ctx.args = []
        ctx._protected_args = []
        if not self.chain:
            cmd_name, cmd, args = self.resolve_command(ctx, args)
            if cmd is None:
                return ctx.fail("Unknown command.")
            ctx.invoked_subcommand = cmd_name
            sub_ctx = cmd.make_context(cmd_name, args, parent=ctx)
            sub_ctx.obj = self.zush_ctx
            with sub_ctx:
                return sub_ctx.command.invoke(sub_ctx)
        return super().invoke(ctx)


def add_reserved_self_group(
    root: click.Group,
    storage: Any | None = None,
    service_controller: ServiceController | None = None,
    loaded_extensions: list[str] | None = None,
    system_commands: dict[str, click.Command | click.Group] | None = None,
    diagnostics: list[DiscoveryDiagnostic] | None = None,
) -> None:
    """Add the reserved 'self' group with built-in zush commands."""
    self_group = click.Group(
        RESERVED_GROUP_NAME,
        help="Reserved: built-in zush commands.",
    )
    map_cmd = click.Command(
        "map",
        callback=_map_callback,
        help="Print command tree (like tree).",
    )
    config_cmd = click.Command(
        "config",
        callback=_config_callback(storage or default_storage()),
        help="Open the target zush config folder.",
    )
    toggle_cmd = click.Command(
        "toggle",
        callback=_toggle_callback(storage or default_storage(), loaded_extensions or []),
        params=[click.Argument(["name"], required=False)],
        help="Inspect or toggle extension loading for future boots.",
    )
    services_cmd = click.Command(
        "services",
        callback=_services_callback(service_controller),
        params=[
            click.Argument(["name"], required=False),
            click.Option(["--start"], is_flag=True, default=False),
            click.Option(["--stop"], is_flag=True, default=False),
            click.Option(["--restart"], is_flag=True, default=False),
            click.Option(["--status"], is_flag=True, default=False),
        ],
        help="Control registered detached services.",
    )
    diagnostics_cmd = click.Command(
        "diagnostics",
        callback=_diagnostics_callback(diagnostics or []),
        help="Print discovery and command registration diagnostics.",
    )
    cron_group = click.Group(
        "cron",
        help="Manage scheduled zush commands stored in cron.json.",
    )
    cron_add_cmd = click.Command(
        "add",
        callback=_cron_add_callback(root, storage or default_storage()),
        params=[
            click.Argument(["schedule"]),
            click.Argument(["command_path"]),
        ],
        help="Add one cron job for a dotted command path.",
        context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
    )
    cron_start_cmd = click.Command(
        "start",
        callback=_cron_start_callback(root, storage or default_storage()),
        help="Start the foreground cron scheduler loop.",
    )
    cron_list_cmd = click.Command(
        "list",
        callback=_cron_list_callback(storage or default_storage()),
        help="List persisted cron jobs.",
    )
    cron_remove_cmd = click.Command(
        "remove",
        callback=_cron_remove_callback(storage or default_storage()),
        params=[click.Argument(["name"])],
        help="Remove one persisted cron job.",
    )
    cron_group.add_command(cron_add_cmd, "add")
    cron_group.add_command(cron_list_cmd, "list")
    cron_group.add_command(cron_remove_cmd, "remove")
    cron_group.add_command(cron_start_cmd, "start")
    self_group.add_command(map_cmd, "map")
    self_group.add_command(config_cmd, "config")
    self_group.add_command(toggle_cmd, "toggle")
    self_group.add_command(services_cmd, "services")
    self_group.add_command(diagnostics_cmd, "diagnostics")
    self_group.add_command(cron_group, "cron")
    for name, command in (system_commands or {}).items():
        if name not in self_group.commands:
            self_group.add_command(command, name)
    root.add_command(self_group, RESERVED_GROUP_NAME)


def _map_callback() -> None:
    """Click callback for 'zush self map'; finds root from context and prints tree."""
    ctx = click.get_current_context()
    root_group = ctx.find_root().command
    if not isinstance(root_group, click.Group):
        raise click.ClickException("Root command tree is unavailable")
    click.echo(root_group.name or "zush")
    _print_command_tree(root_group, "")


def _config_callback(storage: Any):
    """Build the self config callback bound to one storage target."""
    def callback() -> None:
        """Open the active zush config directory for the current storage target."""
        target = Path(storage.config_dir())
        target.mkdir(parents=True, exist_ok=True)
        _open_config_directory(target)

    return callback


def _open_config_directory(target: Path) -> None:
    """Open one config directory in the platform-native file explorer."""
    if sys.platform.startswith("win") and hasattr(os, "startfile"):
        try:
            getattr(os, "startfile")(str(target))
            return
        except OSError as exc:
            raise click.ClickException(f"Failed to open config directory: {target}") from exc

    exit_code = click.launch(str(target))
    if exit_code != 0:
        raise click.ClickException(f"Failed to open config directory: {target}")


def _toggle_callback(storage: Any, loaded_extensions: list[str]):
    """Build the self toggle callback bound to one storage target and boot snapshot."""
    def callback(name: str | None) -> None:
        """Inspect or toggle extension state for the current storage target."""
        if not name:
            _print_toggle_state(storage, loaded_extensions)
            return
        enabled = toggle_extension(name, storage=storage)
        status = "enabled" if enabled else "disabled"
        click.echo(f"{status} {name}")

    return callback


def _print_toggle_state(storage: Any, loaded_extensions: list[str]) -> None:
    """Print the extension loading snapshot for this boot and the next boot config state."""
    config = load_config(storage=storage)
    disabled_extensions = sorted(config.disabled_extensions or [])
    click.echo("Loaded this boot:")
    for name in sorted(loaded_extensions):
        click.echo(name)
    if not loaded_extensions:
        click.echo("(none)")
    click.echo("Disabled next boot:")
    for name in disabled_extensions:
        click.echo(name)
    if not disabled_extensions:
        click.echo("(none)")


def _services_callback(service_controller: ServiceController | None):
    """Build the self services callback bound to one service controller."""
    def callback(
        name: str | None,
        start: bool,
        stop: bool,
        restart: bool,
        status: bool,
    ) -> None:
        """List or operate on plugin-declared detached services."""
        if service_controller is None:
            raise click.ClickException("Service controller is unavailable")
        selected = [start, stop, restart, status]
        if sum(1 for item in selected if item) > 1:
            raise click.ClickException("Choose only one of --start, --stop, --restart, or --status")
        if not name:
            for service_name in service_controller.list_services():
                click.echo(service_name)
            return
        try:
            if start:
                result = service_controller.start(name)
            elif stop:
                result = service_controller.stop(name)
            elif restart:
                result = service_controller.restart(name)
            else:
                result = service_controller.status(name)
        except KeyError as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(result)

    return callback


def _diagnostics_callback(diagnostics: list[DiscoveryDiagnostic]):
    """Build the self diagnostics callback bound to one collected diagnostics snapshot."""
    def callback() -> None:
        """Print collected discovery and merge diagnostics for the current boot."""
        if not diagnostics:
            click.echo("(none)")
            return
        for diagnostic in diagnostics:
            parts = [diagnostic.code]
            if diagnostic.extension_key:
                parts.append(diagnostic.extension_key)
            elif diagnostic.package_path is not None:
                parts.append(diagnostic.package_path.name)
            parts.append(diagnostic.message)
            click.echo(" | ".join(parts))

    return callback


def _cron_add_callback(root: click.Group, storage: Any):
    """Build the self cron add callback bound to one root group and storage target."""
    def callback(schedule: str, command_path: str) -> None:
        """Persist one cron job from a schedule, dotted command path, and trailing command tokens."""
        raw_tokens, name, detach = _parse_cron_add_tokens(list(click.get_current_context().args))
        job_name = add_cron_job(
            root,
            storage,
            schedule=schedule,
            command_path=command_path,
            raw_tokens=raw_tokens,
            name=name,
            detach=detach,
        )
        click.echo(f"added {job_name}")

    return callback


def _parse_cron_add_tokens(tokens: list[str]) -> tuple[list[str], str | None, bool]:
    """Parse trailing self cron add tokens into command args plus optional name and detach flags."""
    remaining = list(tokens)
    detach = False
    name: str | None = None
    while remaining:
        tail = remaining[-1]
        if tail in {"-d", "--detach"}:
            detach = True
            remaining.pop()
            continue
        if len(remaining) >= 2 and remaining[-2] in {"--name", "-n"}:
            name = tail
            remaining = remaining[:-2]
            continue
        if tail.startswith("--name="):
            name = tail.split("=", 1)[1]
            remaining.pop()
            continue
        if tail.startswith("-n="):
            name = tail.split("=", 1)[1]
            remaining.pop()
            continue
        if tail in {"--name", "-n"}:
            raise click.ClickException(f"{tail} requires a value")
        break
    return remaining, name, detach


def _cron_start_callback(root: click.Group, storage: Any):
    """Build the self cron start callback bound to one root group and storage target."""
    def callback() -> None:
        """Start the foreground cron scheduler loop for the active command tree and storage."""
        start_cron_scheduler(root, storage)

    return callback


def _cron_list_callback(storage: Any):
    """Build the self cron list callback bound to one storage target."""
    def callback() -> None:
        """Print persisted cron jobs from the active base cron registry."""
        jobs = list_cron_jobs(storage)
        if not jobs:
            click.echo("(none)")
            return
        for name, job in jobs:
            schedule = str(job.get("schedule") or "")
            command_path = str(job.get("command") or "")
            mode = "detached" if bool(job.get("detach", False)) else "attached"
            last_run = str(job.get("last_run_at") or "never")
            click.echo(f"{name} | {schedule} | {command_path} | {mode} | {last_run}")

    return callback


def _cron_remove_callback(storage: Any):
    """Build the self cron remove callback bound to one storage target."""
    def callback(name: str) -> None:
        """Delete one persisted cron job by name from the active base cron registry."""
        remove_cron_job(storage, name)
        click.echo(f"removed {name}")

    return callback
