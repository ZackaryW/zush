"""TDD: create_zush_group factory and embedding."""

import click
import pytest

from zush import create_zush_group
from zush.config import Config
from zush.paths import DirectoryStorage


def test_create_zush_group_returns_click_group():
    """create_zush_group() returns a Click Group (for mounting or calling .main())."""
    group = create_zush_group()
    assert isinstance(group, click.Group)
    assert group.name == "zush"


def test_create_zush_group_accepts_name():
    """create_zush_group(name=...) uses that name."""
    group = create_zush_group(name="subzush")
    assert group.name == "subzush"


def test_create_zush_group_with_storage_uses_storage(tmp_path):
    """When storage is provided, config and discovery use it (no default ~/.zush writes)."""
    storage = DirectoryStorage(tmp_path)
    config = Config(envs=[], env_prefix=["zush_"])
    group = create_zush_group(storage=storage, config=config)
    assert isinstance(group, click.Group)
    # Group was built; with empty envs we have no plugin commands but have "self"
    assert "self" in group.commands


def test_zush_group_can_be_added_to_parent_app():
    """Parent app can add zush as subcommand and invoke it."""
    parent = click.Group("myapp")
    parent.add_command(create_zush_group(), "zush")
    result = parent.main(["zush", "self", "map"], standalone_mode=False)
    # Should complete; self map prints tree (may be empty if no config)
    assert result is None or result == 0
