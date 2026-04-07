"""Load ~/.zush/config.toml."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from zush.core import storage as _storage

if TYPE_CHECKING:
    from zush.core.storage import ZushStorage


storage = _storage


@dataclass
class Config:
    """Zush config: envs to scan, optional playground, package prefixes, and current-env scanning."""

    envs: list[Path]
    env_prefix: list[str]
    playground: Path | None = None
    include_current_env: bool = True


def default_config() -> Config:
    return Config(envs=[], env_prefix=["zush_"], playground=None, include_current_env=True)


def ensure_config_exists(storage: ZushStorage | None = None) -> Path:
    """Create a bootstrap config.toml when one does not already exist."""
    file_path = storage.config_file() if storage is not None else _storage.config_file()
    if file_path.exists():
        return file_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(_default_config_toml(), encoding="utf-8")
    return file_path


def _default_config_toml() -> str:
    return (
        "envs = []\n"
        'env_prefix = ["zush_"]\n'
        "include_current_env = true\n"
    )


def load_config(storage: ZushStorage | None = None) -> Config:
    """Load config from config.toml. Returns defaults if missing or invalid."""
    default = default_config()
    file_path = ensure_config_exists(storage=storage)
    try:
        with open(file_path, "rb") as handle:
            data = tomllib.load(handle)
    except (tomllib.TOMLDecodeError, OSError):
        return default
    envs_raw = data.get("envs")
    envs = [] if envs_raw is None else [Path(entry) for entry in envs_raw if isinstance(entry, str)]
    env_prefix = data.get("env_prefix")
    if env_prefix is None:
        env_prefix = ["zush_"]
    elif not isinstance(env_prefix, list):
        env_prefix = ["zush_"]
    else:
        env_prefix = [str(value) for value in env_prefix if isinstance(value, str)]
    if not env_prefix:
        env_prefix = ["zush_"]
    playground_raw = data.get("playground")
    playground = Path(playground_raw) if isinstance(playground_raw, str) else None
    include_current_env_raw = data.get("include_current_env", True)
    include_current_env = bool(include_current_env_raw) if isinstance(include_current_env_raw, bool) else True
    return Config(
        envs=envs,
        env_prefix=env_prefix,
        playground=playground,
        include_current_env=include_current_env,
    )
