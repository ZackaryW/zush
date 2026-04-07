"""Scan envs for plugins; load and merge command trees; update cache and sentry."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from zush.core import envs, storage as _storage
from zush.core.cache import is_env_stale, read_cache, read_sentry, write_cache, write_sentry
from zush.configparse.config import Config
from zush.utils.discovery import (
    build_envs_to_scan as _build_envs_to_scan,
    cached_package_paths_for_env as _cached_package_paths_for_env,
    find_sentry_entry as _find_sentry_entry,
    load_cached_plugins as _load_cached_plugins,
    merge_commands_into_tree as _merge_commands_into_tree,
    scan_env_for_plugins as _scan_env_for_plugins,
)

if TYPE_CHECKING:
    from zush.core.storage import ZushStorage


storage = _storage


def run_discovery(
    config: Config,
    mock_path: Path | None = None,
    no_cache: bool = False,
    storage: ZushStorage | None = None,
) -> tuple[list[tuple[Path, object, dict[str, Any]]], dict[str, Any]]:
    """Scan config envs for plugins and return loaded plugins plus merged tree."""
    all_plugins: list[tuple[Path, object, dict[str, Any]]] = []
    merged_tree: dict[str, Any] = {}
    cached_tree = {} if no_cache else read_cache(storage=storage)
    sentry = [] if no_cache else read_sentry(storage=storage)
    cache_entries: list[dict[str, Any]] = []
    envs_to_scan = _build_envs_to_scan(
        config,
        mock_path=mock_path,
        current_site_package_dirs=envs.current_site_package_dirs,
    )

    for env_path in envs_to_scan:
        env_path = Path(env_path)
        if not env_path.is_dir():
            continue
        env_str = str(env_path.resolve())
        if not no_cache:
            sentry_entry = _find_sentry_entry(sentry, env_str, root=True, package=None)
            if not is_env_stale(env_path, sentry_entry):
                cached_paths = _cached_package_paths_for_env(cached_tree, env_path)
                if cached_paths:
                    _load_cached_plugins(
                        cached_paths,
                        all_plugins,
                        merged_tree,
                        _merge_commands_into_tree,
                    )
                continue
        _scan_env_for_plugins(
            env_path,
            config.env_prefix,
            all_plugins,
            merged_tree,
            cache_entries,
            _merge_commands_into_tree,
        )

    if not no_cache and cache_entries:
        write_sentry(cache_entries, storage=storage)
        write_cache(merged_tree, storage=storage)
    return all_plugins, merged_tree
