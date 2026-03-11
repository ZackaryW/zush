"""TDD: plugin_loader — load __zush__.py and get instance + commands dict."""

import tempfile
from pathlib import Path

import click
import pytest

from zush.plugin_loader import load_plugin


def test_load_plugin_missing_file_raises():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "no__zush__"
        with pytest.raises((FileNotFoundError, OSError, ValueError)):
            load_plugin(p)


def test_load_plugin_returns_instance_and_commands(tmp_path):
    """A package dir with __zush__.py that has an instance with .commands is loaded."""
    (tmp_path / "__zush__.py").write_text("""
import click
cmd = click.Command("hello")
plugin = type("Plugin", (), {"commands": {"greet": cmd}})()
""")
    instance, commands = load_plugin(tmp_path)
    assert "greet" in commands
    assert commands["greet"].name == "hello"


def test_load_plugin_accepts_zush_plugin_instance(tmp_path):
    """Plugin can be an instance with a 'commands' dict (ZushPlugin contract)."""
    (tmp_path / "__zush__.py").write_text("""
import click
class ZushPlugin:
    def __init__(self):
        self.commands = {"a": click.Command("a")}
ZushPlugin = ZushPlugin()
""")
    instance, commands = load_plugin(tmp_path)
    assert commands == {"a": instance.commands["a"]}
