"""TDD: config module — load config.toml."""

import tempfile
from pathlib import Path

import pytest

from zush import config as config_module
from zush.config import load_config, Config
from zush.paths import DirectoryStorage


def test_load_config_missing_file_returns_defaults(monkeypatch):
    """When config.toml is missing, return default env_prefix and empty envs."""
    with tempfile.TemporaryDirectory() as d:
        monkeypatch.setattr(config_module.paths, "config_file", lambda: Path(d) / "nonexistent.toml")
        cfg = load_config()
    assert cfg.env_prefix == ["zush_"]
    assert cfg.envs == []
    assert cfg.playground is None
    assert cfg.include_current_env is False


def test_load_config_invalid_toml_returns_defaults(monkeypatch):
    """When config.toml is invalid, return defaults."""
    with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as f:
        f.write(b"not valid toml [[[")
        path = Path(f.name)
    try:
        monkeypatch.setattr(config_module.paths, "config_file", lambda: path)
        cfg = load_config()
        assert cfg.env_prefix == ["zush_"]
        assert cfg.envs == []
        assert cfg.playground is None
        assert cfg.include_current_env is False
    finally:
        path.unlink(missing_ok=True)


def test_load_config_parses_envs_and_prefix(monkeypatch):
    """Parse envs (paths) and env_prefix from config.toml."""
    with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as f:
        f.write(b'envs = ["/foo", "/bar"]\nenv_prefix = ["zush_", "my_"]')
        path = Path(f.name)
    try:
        monkeypatch.setattr(config_module.paths, "config_file", lambda: path)
        cfg = load_config()
        assert cfg.env_prefix == ["zush_", "my_"]
        assert len(cfg.envs) == 2
        assert "foo" in str(cfg.envs[0]) and "bar" in str(cfg.envs[1])
    finally:
        path.unlink(missing_ok=True)


def test_load_config_default_prefix_when_omitted(monkeypatch):
    """When env_prefix is omitted, use ['zush_']."""
    with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as f:
        f.write(b'envs = []')
        path = Path(f.name)
    try:
        monkeypatch.setattr(config_module.paths, "config_file", lambda: path)
        cfg = load_config()
        assert cfg.env_prefix == ["zush_"]
    finally:
        path.unlink(missing_ok=True)


def test_config_has_envs_and_env_prefix():
    """Config type has envs and env_prefix."""
    cfg = Config(envs=[], env_prefix=["zush_"])
    assert cfg.envs == []
    assert cfg.env_prefix == ["zush_"]


def test_load_config_include_current_env_optional(monkeypatch):
    """include_current_env is optional; when set to true, flag is True."""
    with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as f:
        f.write(b'envs = []\ninclude_current_env = true')
        path = Path(f.name)
    try:
        monkeypatch.setattr(config_module.paths, "config_file", lambda: path)
        cfg = load_config()
        assert cfg.include_current_env is True
    finally:
        path.unlink(missing_ok=True)


def test_load_config_playground_optional(monkeypatch):
    """playground is optional; when set, it is a Path."""
    with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as f:
        f.write(b'envs = []\nplayground = "/play"')
        path = Path(f.name)
    try:
        monkeypatch.setattr(config_module.paths, "config_file", lambda: path)
        cfg = load_config()
        assert cfg.playground is not None
        assert "play" in str(cfg.playground)
    finally:
        path.unlink(missing_ok=True)


def test_load_config_uses_storage_when_provided(tmp_path):
    """When storage is provided, load from storage.config_file()."""
    config_path = tmp_path / "config.toml"
    config_path.write_text('envs = ["/custom/env"]\nenv_prefix = ["custom_"]', encoding="utf-8")
    storage = DirectoryStorage(tmp_path)
    cfg = load_config(storage=storage)
    assert len(cfg.envs) == 1
    assert "custom" in str(cfg.envs[0])
    assert cfg.env_prefix == ["custom_"]
