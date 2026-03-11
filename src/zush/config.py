"""Load ~/.zush/config.toml."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from zush import paths

if TYPE_CHECKING:
    from zush.paths import ZushStorage


@dataclass
class Config:
    """Zush config: envs to scan, optional playground (overloaded index env), and package name prefix."""

    envs: list[Path]
    env_prefix: list[str]
    playground: Path | None = None


def load_config(storage: ZushStorage | None = None) -> Config:
    """Load config from config.toml. Uses storage.config_file() when provided, else default paths. Returns defaults if missing or invalid."""
    default = Config(envs=[], env_prefix=["zush_"], playground=None)
    p = storage.config_file() if storage is not None else paths.config_file()
    if not p.exists():
        return default
    try:
        with open(p, "rb") as f:
            data = tomllib.load(f)
    except (tomllib.TOMLDecodeError, OSError):
        return default
    envs_raw = data.get("envs")
    if envs_raw is None:
        envs = []
    else:
        envs = [Path(e) for e in envs_raw if isinstance(e, str)]
    env_prefix = data.get("env_prefix")
    if env_prefix is None:
        env_prefix = ["zush_"]
    elif not isinstance(env_prefix, list):
        env_prefix = ["zush_"]
    else:
        env_prefix = [str(x) for x in env_prefix if isinstance(x, str)]
    if not env_prefix:
        env_prefix = ["zush_"]
    playground_raw = data.get("playground")
    playground = Path(playground_raw) if isinstance(playground_raw, str) else None
    return Config(envs=envs, env_prefix=env_prefix, playground=playground)
