"""Cache and sentry read/write; staleness check for envs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from zush import paths

if TYPE_CHECKING:
    from zush.paths import ZushStorage


def read_cache(storage: ZushStorage | None = None) -> dict[str, Any]:
    """Read cache.json. Uses storage.cache_file() when provided, else default path. Returns {} if missing or invalid."""
    p = storage.cache_file() if storage is not None else paths.cache_file()
    if not p.exists():
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def write_cache(data: dict[str, Any], storage: ZushStorage | None = None) -> None:
    """Write cache.json. Uses storage.cache_file() when provided. Creates parent dir if needed."""
    p = storage.cache_file() if storage is not None else paths.cache_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def read_sentry(storage: ZushStorage | None = None) -> list[dict[str, Any]]:
    """Read sentry.json. Uses storage.sentry_file() when provided. Returns [] if missing or invalid."""
    p = storage.sentry_file() if storage is not None else paths.sentry_file()
    if not p.exists():
        return []
    try:
        with open(p, encoding="utf-8") as f:
            out = json.load(f)
            return out if isinstance(out, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def write_sentry(data: list[dict[str, Any]], storage: ZushStorage | None = None) -> None:
    """Write sentry.json. Uses storage.sentry_file() when provided. Creates parent dir if needed."""
    p = storage.sentry_file() if storage is not None else paths.sentry_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def is_env_stale(env_path: Path, sentry_entry: dict[str, Any] | None) -> bool:
    """True if env should be re-scanned (no entry or mtime > last_cached)."""
    if sentry_entry is None:
        return True
    try:
        mtime = env_path.stat().st_mtime
        last = sentry_entry.get("last_cached")
        if last is None:
            return True
        return mtime > float(last)
    except OSError:
        return True
