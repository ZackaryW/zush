from __future__ import annotations

import click
from typing import Any


RESERVED_GROUP_NAME = "self"


def merge_commands_into_group(
    group: click.Group,
    plugin_list: list[tuple[Any, Any, dict[str, click.Command | click.Group]]],
) -> None:
    """Merge each plugin's commands dict into group. Dotted keys become nested groups."""
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


def command_path(ctx: click.Context) -> list[str]:
    protected = getattr(ctx, "_protected_args", []) or []
    return list(protected) + list(ctx.args)


def print_command_tree(group: click.Group, prefix: str) -> None:
    names = sorted(group.commands.keys())
    for index, child_name in enumerate(names):
        last = index == len(names) - 1
        branch = "└── " if last else "├── "
        click.echo(prefix + branch + child_name)
        cmd = group.commands[child_name]
        if isinstance(cmd, click.Group):
            new_prefix = prefix + ("    " if last else "│   ")
            print_command_tree(cmd, new_prefix)
