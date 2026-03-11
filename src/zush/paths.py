"""Config dir and file paths for ~/.zush."""

from pathlib import Path


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
