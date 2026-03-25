"""TDD: paths module — config dir and file paths; storage protocol and default."""

import pytest
from pathlib import Path

from zush.paths import (
    config_dir,
    config_file,
    cache_file,
    sentry_file,
    services_file,
    cfg_index_file,
    cfg_dir,
    default_storage,
    DirectoryStorage,
    temporary_storage,
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


def test_services_file_is_under_config_dir():
    assert services_file().parent == config_dir()
    assert services_file().name == "services.json"


def test_cfg_index_file_is_under_config_dir():
    assert cfg_index_file().parent == config_dir()
    assert cfg_index_file().name == "cfg-index.json"


def test_cfg_dir_is_under_config_dir():
    assert cfg_dir().parent == config_dir()
    assert cfg_dir().name == "cfgs"


# --- Storage protocol and default ---


def test_default_storage_returns_storage_with_required_paths():
    s = default_storage()
    assert s is not None
    assert hasattr(s, "config_dir") and callable(s.config_dir)
    assert hasattr(s, "config_file") and callable(s.config_file)
    assert hasattr(s, "cache_file") and callable(s.cache_file)
    assert hasattr(s, "sentry_file") and callable(s.sentry_file)
    assert hasattr(s, "services_file") and callable(s.services_file)
    assert hasattr(s, "cfg_index_file") and callable(s.cfg_index_file)
    assert hasattr(s, "cfg_dir") and callable(s.cfg_dir)


def test_default_storage_paths_match_legacy_paths():
    s = default_storage()
    assert s.config_dir() == config_dir()
    assert s.config_file() == config_file()
    assert s.cache_file() == cache_file()
    assert s.sentry_file() == sentry_file()
    assert s.services_file() == services_file()
    assert s.cfg_index_file() == cfg_index_file()
    assert s.cfg_dir() == cfg_dir()


def test_directory_storage_uses_given_base_path(tmp_path):
    s = DirectoryStorage(tmp_path)
    assert s.config_dir() == tmp_path
    assert s.config_file() == tmp_path / "config.toml"
    assert s.cache_file() == tmp_path / "cache.json"
    assert s.sentry_file() == tmp_path / "sentry.json"
    assert s.services_file() == tmp_path / "services.json"
    assert s.cfg_index_file() == tmp_path / "cfg-index.json"
    assert s.cfg_dir() == tmp_path / "cfgs"


def test_temporary_storage_yields_directory_storage_and_cleans_up() -> None:
    with temporary_storage() as storage:
        base = storage.config_dir()
        assert isinstance(storage, DirectoryStorage)
        assert base.exists()
        assert storage.config_file().parent == base
        assert storage.cache_file().parent == base
        assert storage.sentry_file().parent == base
        assert storage.services_file().parent == base
        assert storage.cfg_index_file().parent == base
        assert storage.cfg_dir().parent == base
    assert not base.exists()
