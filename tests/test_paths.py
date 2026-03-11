"""TDD: paths module — config dir and file paths; storage protocol and default."""

import pytest
from pathlib import Path

from zush.paths import (
    config_dir,
    config_file,
    cache_file,
    sentry_file,
    default_storage,
    DirectoryStorage,
)


def test_config_dir_returns_path_under_home():
    d = config_dir()
    assert isinstance(d, Path)
    assert d.name == ".zush"
    assert Path.home() in d.parents or d == Path.home() / ".zush"


def test_config_file_is_under_config_dir():
    assert config_file().parent == config_dir()
    assert config_file().name == "config.toml"


def test_cache_file_is_under_config_dir():
    assert cache_file().parent == config_dir()
    assert cache_file().name == "cache.json"


def test_sentry_file_is_under_config_dir():
    assert sentry_file().parent == config_dir()
    assert sentry_file().name == "sentry.json"


# --- Storage protocol and default ---


def test_default_storage_returns_storage_with_required_paths():
    s = default_storage()
    assert s is not None
    assert hasattr(s, "config_dir") and callable(s.config_dir)
    assert hasattr(s, "config_file") and callable(s.config_file)
    assert hasattr(s, "cache_file") and callable(s.cache_file)
    assert hasattr(s, "sentry_file") and callable(s.sentry_file)


def test_default_storage_paths_match_legacy_paths():
    s = default_storage()
    assert s.config_dir() == config_dir()
    assert s.config_file() == config_file()
    assert s.cache_file() == cache_file()
    assert s.sentry_file() == sentry_file()


def test_directory_storage_uses_given_base_path(tmp_path):
    s = DirectoryStorage(tmp_path)
    assert s.config_dir() == tmp_path
    assert s.config_file() == tmp_path / "config.toml"
    assert s.cache_file() == tmp_path / "cache.json"
    assert s.sentry_file() == tmp_path / "sentry.json"
