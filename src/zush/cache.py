"""Cache and sentry read/write; staleness check for envs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from zush import paths


def read_cache() -> dict[str, Any]:
    """Read cache.json. Returns {} if missing or invalid."""
    p = paths.cache_file()
    if not p.exists():
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def write_cache(data: dict[str, Any]) -> None:
    """Write cache.json. Creates parent dir if needed."""
    p = paths.cache_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def read_sentry() -> list[dict[str, Any]]:
    """Read sentry.json. Returns [] if missing or invalid."""
    p = paths.sentry_file()
    if not p.exists():
        return []
    try:
        with open(p, encoding="utf-8") as f:
            out = json.load(f)
            return out if isinstance(out, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def write_sentry(data: list[dict[str, Any]]) -> None:
    """Write sentry.json. Creates parent dir if needed."""
    p = paths.sentry_file()
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
