"""TDD: discovery — scan envs, load plugins, merge tree, update cache/sentry."""

import tempfile
from pathlib import Path

import click
import pytest

from zush.config import Config
from zush.discovery import run_discovery
from zush.cache import read_cache, read_sentry


def test_run_discovery_empty_envs_returns_empty_plugin_list(monkeypatch):
    with tempfile.TemporaryDirectory() as d:
        monkeypatch.setattr("zush.discovery.paths.config_dir", lambda: Path(d))
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
        monkeypatch.setattr("zush.discovery.paths.config_dir", lambda: config_dir)
        monkeypatch.setattr("zush.discovery.paths.cache_file", lambda: config_dir / "cache.json")
        monkeypatch.setattr("zush.discovery.paths.sentry_file", lambda: config_dir / "sentry.json")
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
        monkeypatch.setattr("zush.discovery.paths.config_dir", lambda: config_dir)
        monkeypatch.setattr("zush.discovery.paths.cache_file", lambda: config_dir / "cache.json")
        monkeypatch.setattr("zush.discovery.paths.sentry_file", lambda: config_dir / "sentry.json")
        cfg = Config(envs=[], env_prefix=["zush_"], playground=env_path)
        plugins, _ = run_discovery(cfg)
    assert len(plugins) == 1
    assert plugins[0][0] == pkg
