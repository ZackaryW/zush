"""TDD: ZushGroup and merge_commands_into_group."""

import re
from pathlib import Path

import click
import pytest
from click.testing import CliRunner

from zush.context import ZushCtx, HookRegistry
from zush.group import ZushGroup, add_reserved_self_group, merge_commands_into_group
from zush.paths import DirectoryStorage


def _invoke(group: click.Group, args: list[str]) -> click.Context:
    """Invoke group with args and return the context (after full invoke)."""
    ctx = group.make_context("zush", list(args))
    with ctx:
        group.invoke(ctx)
    return ctx


def test_merge_commands_into_group_adds_command():
    """Single command is added to group."""
    root = click.Group("root")
    commands = {"hello": click.Command("hello", callback=lambda: None)}
    merge_commands_into_group(root, [("/p", None, commands)])
    assert "hello" in root.commands
    assert root.commands["hello"].name == "hello"


def test_merge_commands_into_group_nested():
    """Dotted key creates nested groups and command."""
    root = click.Group("root")
    cmd = click.Command("run", callback=lambda: None)
    commands = {"foo.bar.run": cmd}
    merge_commands_into_group(root, [("/p", None, commands)])
    assert "foo" in root.commands
    foo = root.commands["foo"]
    assert isinstance(foo, click.Group)
    assert "bar" in foo.commands
    bar = foo.commands["bar"]
    assert isinstance(bar, click.Group)
    assert "run" in bar.commands


def test_self_is_reserved_group():
    """Plugin commands under 'self' are not merged; reserved for built-in."""
    root = click.Group("root")
    commands = {"self.foo": click.Command("foo", callback=lambda: None)}
    merge_commands_into_group(root, [("/p", None, commands)])
    assert "self" not in root.commands


def test_merge_commands_first_wins():
    """First plugin to register a path wins (overloaded index / playground)."""
    root = click.Group("root")
    cmd1 = click.Command("first", callback=lambda: None)
    cmd2 = click.Command("second", callback=lambda: None)
    merge_commands_into_group(root, [
        ("/playground", None, {"hello": cmd1}),
        ("/other", None, {"hello": cmd2}),
    ])
    assert root.commands["hello"].name == "first"


def test_zush_group_sets_ctx_obj():
    """ZushGroup sets ctx.obj to ZushCtx so commands can access it."""
    zush_ctx = ZushCtx()
    hooks = HookRegistry()
    seen_obj = []
    root = ZushGroup("zush", zush_ctx=zush_ctx, hook_registry=hooks)

    @click.pass_context
    def check(ctx):
        seen_obj.append(ctx.obj)

    root.add_command(click.Command("check", callback=check), "check")
    _invoke(root, ["check"])
    assert len(seen_obj) == 1
    # Command receives the same object the group stores (sub_ctx.obj = self.zush_ctx)
    assert seen_obj[0] is root.zush_ctx


def test_zush_group_runs_before_and_after_hooks():
    """beforeCmd and afterCmd run around command."""
    zush_ctx = ZushCtx()
    hooks = HookRegistry()
    order = []
    hooks.register_before_cmd(re.compile(".*"), lambda p: order.append(("before", p)))
    hooks.register_after_cmd(re.compile(".*"), lambda p: order.append(("after", p)))
    root = ZushGroup("zush", zush_ctx=zush_ctx, hook_registry=hooks)
    root.add_command(click.Command("x", callback=lambda: order.append("cmd")), "x")

    _invoke(root, ["x"])
    assert order == [("before", "x"), "cmd", ("after", "x")]


def test_zush_group_runs_on_error_on_exception():
    """onError runs when command raises matching exception."""
    zush_ctx = ZushCtx()
    hooks = HookRegistry()
    caught = []
    hooks.register_on_error(ValueError, lambda e: caught.append(e))
    root = ZushGroup("zush", zush_ctx=zush_ctx, hook_registry=hooks)

    def fail():
        raise ValueError("oops")

    root.add_command(click.Command("fail", callback=fail), "fail")
    with pytest.raises(ValueError):
        _invoke(root, ["fail"])
    assert len(caught) == 1
    assert caught[0].args == ("oops",)


def test_self_map_shows_live_root_commands() -> None:
    """self map should print the full root tree, not only the reserved self group."""
    root = ZushGroup("zush")
    root.add_command(click.Command("applewood", callback=lambda: None), "applewood")
    add_reserved_self_group(root)

    result = CliRunner().invoke(root, ["self", "map"])

    assert result.exit_code == 0
    assert "applewood" in result.output
    assert "self" in result.output


def test_self_config_opens_storage_config_dir(monkeypatch, tmp_path: Path) -> None:
    launched: list[str] = []
    storage = DirectoryStorage(tmp_path)
    root = ZushGroup("zush")

    monkeypatch.setattr(click, "launch", lambda value, locate=False: launched.append(value) or 0)

    add_reserved_self_group(root, storage=storage)
    result = CliRunner().invoke(root, ["self", "config"])

    assert result.exit_code == 0
    assert launched == [str(tmp_path)]
    assert tmp_path.exists()
