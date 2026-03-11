"""TDD: paths module — config dir and file paths."""

import pytest
from pathlib import Path

from zush.paths import config_dir, config_file, cache_file, sentry_file


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
