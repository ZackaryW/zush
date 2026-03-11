"""Tests for zush.plugin helper (Plugin / Section)."""

import click
import pytest

from zush.plugin import Plugin, Section


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
