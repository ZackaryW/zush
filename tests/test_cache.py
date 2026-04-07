"""TDD: cache module — cache.json and sentry.json read/write, staleness."""

import json
import tempfile
from pathlib import Path

import pytest

from zush.core import cache as cache_module
from zush.core.cache import (
    read_cache,
    write_cache,
    read_sentry,
    write_sentry,
    is_env_stale,
)
from zush.core.storage import DirectoryStorage


def test_read_cache_missing_returns_empty_dict(monkeypatch):
    monkeypatch.setattr(cache_module.storage, "cache_file", lambda: Path("/nonexistent/cache.json"))
    assert read_cache() == {}


def test_read_cache_invalid_json_returns_empty_dict(monkeypatch):
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        f.write(b"not json {")
        path = Path(f.name)
    try:
        monkeypatch.setattr(cache_module.storage, "cache_file", lambda: path)
        assert read_cache() == {}
    finally:
        path.unlink(missing_ok=True)


def test_write_and_read_cache(monkeypatch):
    with tempfile.TemporaryDirectory() as d:
        cache_path = Path(d) / "cache.json"
        monkeypatch.setattr(cache_module.storage, "cache_file", lambda: cache_path)
        data = {"a": {"_zushtype": "path", "path": "/p", "exported": ["b"]}}
        write_cache(data)
        assert read_cache() == data


def test_read_sentry_missing_returns_empty_list(monkeypatch):
    monkeypatch.setattr(cache_module.storage, "sentry_file", lambda: Path("/nonexistent/sentry.json"))
    assert read_sentry() == []


def test_write_and_read_sentry(monkeypatch):
    with tempfile.TemporaryDirectory() as d:
        sentry_path = Path(d) / "sentry.json"
        monkeypatch.setattr(cache_module.storage, "sentry_file", lambda: sentry_path)
        data = [{"env": "/e", "root": True, "last_cached": 123.0}]
        write_sentry(data)
        assert read_sentry() == data


def test_is_env_stale_no_sentry_entry_returns_true():
    """When there is no sentry entry for the path, consider stale."""
    assert is_env_stale(Path("/some/env"), None) is True


def test_is_env_stale_mtime_greater_than_last_cached_returns_true(monkeypatch):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        entry = {"env": str(p), "root": True, "last_cached": 0.0}
        assert is_env_stale(p, entry) is True


def test_is_env_stale_mtime_equal_returns_false(monkeypatch):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        mtime = p.stat().st_mtime
        entry = {"env": str(p), "root": True, "last_cached": mtime}
        assert is_env_stale(p, entry) is False


def test_read_write_cache_use_storage_when_provided(tmp_path):
    """When storage is provided, read_cache/write_cache use storage.cache_file()."""
    storage = DirectoryStorage(tmp_path)
    data = {"x": {"_zushtype": "path", "exported": ["y"]}}
    write_cache(data, storage=storage)
    assert (tmp_path / "cache.json").exists()
    assert read_cache(storage=storage) == data


def test_read_write_sentry_use_storage_when_provided(tmp_path):
    """When storage is provided, read_sentry/write_sentry use storage.sentry_file()."""
    storage = DirectoryStorage(tmp_path)
    data = [{"env": "/e", "root": True, "last_cached": 1.0}]
    write_sentry(data, storage=storage)
    assert (tmp_path / "sentry.json").exists()
    assert read_sentry(storage=storage) == data
