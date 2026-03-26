"""Tests for zush.plugin helper (Plugin / Section)."""

import click
import pytest
from click.testing import CliRunner

from zush.plugin import Plugin, Section
from zush.group import ZushGroup, merge_commands_into_group


def test_plugin_group_and_command_build_commands_dict() -> None:
    """Plugin().group(...).command(...) produces the expected dotted keys."""
    p = Plugin()
    p.group("demo", help="Demo").command("greet", callback=lambda: None, help="Greet")
    assert "demo" in p.commands
    assert "demo.greet" in p.commands
    assert isinstance(p.commands["demo"], click.Group)
    assert isinstance(p.commands["demo.greet"], click.Command)


def test_plugin_nested_groups() -> None:
    """Chained .group() creates nested groups with correct keys."""
    p = Plugin()
    p.group("a", help="A").group("b", help="B").group("c", help="C").command(
        "run", callback=lambda: None
    )
    assert "a" in p.commands
    assert "a.b" in p.commands
    assert "a.b.c" in p.commands
    assert "a.b.c.run" in p.commands


def test_section_returns_self_from_command_for_chaining() -> None:
    """Section.command() returns self so multiple commands can be added under same group."""
    p = Plugin()
    section = p.group("g", help="G")
    section.command("one", callback=lambda: None).command("two", callback=lambda: None)
    assert "g.one" in p.commands
    assert "g.two" in p.commands


def test_plugin_instance_has_commands_for_loader() -> None:
    """Plugin instance exposes .commands dict as expected by the loader."""
    p = Plugin()
    p.group("x", help="X").command("y", callback=lambda: None)
    assert hasattr(p, "commands")
    assert isinstance(p.commands, dict)
    assert set(p.commands.keys()) == {"x", "x.y"}


def test_plugin_helper_parent_help_includes_command_signature_summary() -> None:
    """Parent help should include child command arg and option specs, not just prose help."""
    p = Plugin()
    p.group("clone", help="Clone tools").command(
        "add",
        callback=lambda source, force: None,
        help="Register a clone source for project sync.",
        params=[
            click.Argument(["source"], required=False),
            click.Option(["--force"], is_flag=True, default=False),
        ],
    )
    root = ZushGroup("pvt")
    merge_commands_into_group(root, [("/plugin", p, p.commands)])

    result = CliRunner().invoke(root, ["clone", "--help"])

    assert result.exit_code == 0
    assert "Commands:" in result.output
    assert "[OPTIONS] [SOURCE] Register a clone source for project sync." in result.output


def test_plugin_helper_short_help_respects_limit_for_long_signatures() -> None:
    """Long helper-built signatures should still honor Click's short-help width limit."""
    p = Plugin()
    p.group("clone", help="Clone tools").command(
        "add",
        callback=lambda *args: None,
        help="Register a clone source for project sync.",
        params=[
            click.Argument(["source"]),
            click.Argument(["destination"]),
            click.Argument(["profile_name"]),
            click.Argument(["environment_name"]),
            click.Argument(["migration_target"]),
        ],
    )

    summary = p.commands["clone.add"].get_short_help_str(45)

    assert len(summary) <= 45
    assert summary.endswith("...")
    assert summary.startswith("[OPTIONS] SOURCE")
