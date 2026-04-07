"""TDD: discovery — scan envs, load plugins, merge tree, update cache/sentry."""

import tempfile
from pathlib import Path

import click
import pytest

from zush.configparse.config import Config
from zush.core.cache import read_cache, read_sentry
from zush.core.discovery import run_discovery
from zush.core.storage import DirectoryStorage


def test_run_discovery_empty_envs_returns_empty_plugin_list(monkeypatch):
    with tempfile.TemporaryDirectory() as d:
        monkeypatch.setattr("zush.core.discovery.storage.config_dir", lambda: Path(d))
        cfg = Config(envs=[], env_prefix=["zush_"])
        plugins, _ = run_discovery(cfg)
    assert plugins == []


def test_run_discovery_discovers_plugin_and_updates_cache(monkeypatch):
    with tempfile.TemporaryDirectory() as env_root:
        env_path = Path(env_root)
        pkg = env_path / "zush_foo"
        pkg.mkdir()
        (pkg / "__zush__.py").write_text("""
import click
plugin = type("P", (), {"commands": {"hello": click.Command("hello")}})()
""")
        config_dir = Path(tempfile.mkdtemp())
        monkeypatch.setattr("zush.core.discovery.storage.config_dir", lambda: config_dir)
        monkeypatch.setattr("zush.core.discovery.storage.cache_file", lambda: config_dir / "cache.json")
        monkeypatch.setattr("zush.core.discovery.storage.sentry_file", lambda: config_dir / "sentry.json")
        cfg = Config(envs=[env_path], env_prefix=["zush_"])
        plugins, tree = run_discovery(cfg)
    assert len(plugins) == 1
    path, instance, commands = plugins[0]
    assert path == pkg
    assert "hello" in commands
    assert "hello" in tree or any("hello" in str(n) for n in _nodes(tree))
    cache = read_cache()
    assert cache != {}
    sentry = read_sentry()
    assert len(sentry) >= 1


def _nodes(d):
    """Flatten nested dict keys."""
    for k, v in (d or {}).items():
        if k.startswith("_"):
            continue
        yield k
        if isinstance(v, dict):
            yield from _nodes(v)


def test_run_discovery_uses_playground_as_overloaded_index(monkeypatch):
    """When config.playground is set, it is scanned first (overloaded index env)."""
    with tempfile.TemporaryDirectory() as env_root:
        env_path = Path(env_root)
        pkg = env_path / "zush_foo"
        pkg.mkdir()
        (pkg / "__zush__.py").write_text("""
import click
plugin = type("P", (), {"commands": {"hello": click.Command("hello", callback=lambda: None)}})()
""")
        config_dir = Path(tempfile.mkdtemp())
        monkeypatch.setattr("zush.core.discovery.storage.config_dir", lambda: config_dir)
        monkeypatch.setattr("zush.core.discovery.storage.cache_file", lambda: config_dir / "cache.json")
        monkeypatch.setattr("zush.core.discovery.storage.sentry_file", lambda: config_dir / "sentry.json")
        cfg = Config(envs=[], env_prefix=["zush_"], playground=env_path)
        plugins, _ = run_discovery(cfg)
    assert len(plugins) == 1
    assert plugins[0][0] == pkg


def test_run_discovery_uses_storage_when_provided(tmp_path):
    """When storage is provided, cache and sentry are read/written via storage."""
    env_root = tmp_path / "env"
    env_root.mkdir()
    pkg = env_root / "zush_foo"
    pkg.mkdir()
    (pkg / "__zush__.py").write_text("""
import click
plugin = type("P", (), {"commands": {"hi": click.Command("hi")}})()
""")
    storage = DirectoryStorage(tmp_path / "data")
    cfg = Config(envs=[env_root], env_prefix=["zush_"])
    plugins, tree = run_discovery(cfg, storage=storage)
    assert len(plugins) == 1
    assert (storage.cache_file()).exists()
    assert (storage.sentry_file()).exists()
    assert read_cache(storage=storage) != {}
    assert len(read_sentry(storage=storage)) >= 1


def test_run_discovery_includes_current_env_when_flag_set(monkeypatch, tmp_path):
    """When include_current_env is True, discovery scans current site-packages (via helper)."""
    # Fake current site-packages to point at our temp env_root
    env_root = tmp_path / "env"
    env_root.mkdir()
    pkg = env_root / "zush_foo"
    pkg.mkdir()
    (pkg / "__zush__.py").write_text(
        """
import click
plugin = type("P", (), {"commands": {"hello": click.Command("hello")}})()
"""
    )
    monkeypatch.setattr("zush.core.envs.current_site_package_dirs", lambda: [env_root])
    cfg = Config(envs=[], env_prefix=["zush_"], playground=None, include_current_env=True)
    plugins, _ = run_discovery(cfg)
    assert any(p[0] == pkg for p in plugins)


def test_run_discovery_reloads_cached_plugins_for_unchanged_env(tmp_path):
    """When an env is unchanged, discovery should rebuild live plugins from cache."""
    env_root = tmp_path / "env"
    env_root.mkdir()
    pkg = env_root / "zush_foo"
    pkg.mkdir()
    (pkg / "__zush__.py").write_text(
        """
import click
plugin = type("P", (), {"commands": {"hello": click.Command("hello")}})()
"""
    )
    storage = DirectoryStorage(tmp_path / "data")
    cfg = Config(envs=[env_root], env_prefix=["zush_"])

    first_plugins, first_tree = run_discovery(cfg, storage=storage)

    assert len(first_plugins) == 1
    assert "hello" in first_tree

    second_plugins, second_tree = run_discovery(cfg, storage=storage)

    assert len(second_plugins) == 1
    assert second_plugins[0][0] == pkg
    assert "hello" in second_tree
