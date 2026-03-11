"""Config dir and file paths for ~/.zush; storage protocol for pluggable paths."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


def config_dir() -> Path:
    """Return the zush config directory (e.g. ~/.zush)."""
    return Path.home() / ".zush"


def config_file() -> Path:
    """Return path to config.toml."""
    return config_dir() / "config.toml"


def cache_file() -> Path:
    """Return path to cache.json."""
    return config_dir() / "cache.json"


def sentry_file() -> Path:
    """Return path to sentry.json."""
    return config_dir() / "sentry.json"


class ZushStorage(Protocol):
    """Protocol for config/cache/sentry paths. Enables custom base dir when embedding zush."""

    def config_dir(self) -> Path: ...
    def config_file(self) -> Path: ...
    def cache_file(self) -> Path: ...
    def sentry_file(self) -> Path: ...


class _DefaultStorage:
    """Default storage: paths under ~/.zush (same as legacy paths.*)."""

    def config_dir(self) -> Path:
        return config_dir()

    def config_file(self) -> Path:
        return config_file()

    def cache_file(self) -> Path:
        return cache_file()

    def sentry_file(self) -> Path:
        return sentry_file()


def default_storage() -> _DefaultStorage:
    """Return the default storage (paths under ~/.zush)."""
    return _DefaultStorage()


class DirectoryStorage:
    """Storage that uses a given directory for all paths (config.toml, cache.json, sentry.json)."""

    def __init__(self, base: Path) -> None:
        self._base = Path(base)

    def config_dir(self) -> Path:
        return self._base

    def config_file(self) -> Path:
        return self._base / "config.toml"

    def cache_file(self) -> Path:
        return self._base / "cache.json"

    def sentry_file(self) -> Path:
        return self._base / "sentry.json"
