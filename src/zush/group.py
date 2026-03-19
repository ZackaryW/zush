"""Custom Click group with ZushCtx and hooks; merge plugin commands into group."""

from __future__ import annotations

import click
from typing import Any

from zush.context import ZushCtx, HookRegistry

RESERVED_GROUP_NAME = "self"


def merge_commands_into_group(
    group: click.Group,
    plugin_list: list[tuple[Any, Any, dict[str, click.Command | click.Group]]],
) -> None:
    """Merge each plugin's commands dict into group. Dotted keys become nested groups.
    First plugin to register a given path wins (overloaded index env, e.g. playground, takes precedence).
    """
    for _path, _instance, commands in plugin_list:
        for key, obj in commands.items():
            parts = key.split(".")
            if parts[0] == RESERVED_GROUP_NAME:
                continue
            current = group
            for part in parts[:-1]:
                if part not in current.commands:
                    current.add_command(click.Group(part), part)
                current = current.commands[part]
            name = parts[-1]
            if name not in current.commands:
                current.add_command(obj, name)


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
            result = self._invoke_with_hooks(ctx, path_str)
            self.hook_registry.run_after_cmd(path_str)
            return result
        except BaseException as e:
            self.hook_registry.run_on_error(e)
            raise

    def _invoke_with_hooks(self, ctx: click.Context, path_str: str) -> Any:
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


def _command_path(ctx: click.Context) -> list[str]:
    """Build command path: remaining args / protected_args form the subcommand chain."""
    protected = getattr(ctx, "_protected_args", []) or []
    return list(protected) + list(ctx.args)


def add_reserved_self_group(root: click.Group) -> None:
    """Add the reserved 'self' group with a 'map' command that prints the command tree."""
    self_group = click.Group(
        RESERVED_GROUP_NAME,
        help="Reserved: built-in zush commands.",
    )
    map_cmd = click.Command(
        "map",
        callback=_map_callback,
        help="Print command tree (like tree).",
    )
    self_group.add_command(map_cmd, "map")
    root.add_command(self_group, RESERVED_GROUP_NAME)


def _map_callback() -> None:
    """Click callback for 'zush self map'; finds root from context and prints tree."""
    ctx = click.get_current_context()
    root_group = ctx.find_root().command
    click.echo(root_group.name or "zush")
    _print_command_tree(root_group, "")


def _print_command_tree(group: click.Group, prefix: str) -> None:
    """Print children of group with tree-style chars; recurse for nested groups."""
    names = sorted(group.commands.keys())
    for i, child_name in enumerate(names):
        last = i == len(names) - 1
        branch = "└── " if last else "├── "
        click.echo(prefix + branch + child_name)
        cmd = group.commands[child_name]
        if isinstance(cmd, click.Group):
            new_prefix = prefix + ("    " if last else "│   ")
            _print_command_tree(cmd, new_prefix)
