"""Cache and sentry read/write; staleness check for envs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from zush.core import storage as _storage

if TYPE_CHECKING:
    from zush.core.storage import ZushStorage


storage = _storage


def read_cache(storage: ZushStorage | None = None) -> dict[str, Any]:
    """Read cache.json. Returns {} if missing or invalid."""
    file_path = storage.cache_file() if storage is not None else _storage.cache_file()
    if not file_path.exists():
        return {}
    try:
        with open(file_path, encoding="utf-8") as handle:
            return json.load(handle)
    except (json.JSONDecodeError, OSError):
        return {}


def write_cache(data: dict[str, Any], storage: ZushStorage | None = None) -> None:
    """Write cache.json, creating the parent directory when needed."""
    file_path = storage.cache_file() if storage is not None else _storage.cache_file()
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)


def read_sentry(storage: ZushStorage | None = None) -> list[dict[str, Any]]:
    """Read sentry.json. Returns [] if missing or invalid."""
    file_path = storage.sentry_file() if storage is not None else _storage.sentry_file()
    if not file_path.exists():
        return []
    try:
        with open(file_path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except (json.JSONDecodeError, OSError):
        return []
    return payload if isinstance(payload, list) else []


def write_sentry(data: list[dict[str, Any]], storage: ZushStorage | None = None) -> None:
    """Write sentry.json, creating the parent directory when needed."""
    file_path = storage.sentry_file() if storage is not None else _storage.sentry_file()
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)


def is_env_stale(env_path: Path, sentry_entry: dict[str, Any] | None) -> bool:
    """True if env should be re-scanned (no entry or mtime > last_cached)."""
    if sentry_entry is None:
        return True
    try:
        mtime = env_path.stat().st_mtime
        last_cached = sentry_entry.get("last_cached")
        if last_cached is None:
            return True
        return mtime > float(last_cached)
    except OSError:
        return True
