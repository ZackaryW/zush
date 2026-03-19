"""Scan envs for plugins; load and merge command trees; update cache and sentry."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from zush import paths, envs
from zush.cache import read_cache, write_cache, read_sentry, write_sentry, is_env_stale
from zush.config import Config
from zush.plugin_loader import load_plugin

if TYPE_CHECKING:
    from zush.paths import ZushStorage


def run_discovery(
    config: Config,
    mock_path: Path | None = None,
    no_cache: bool = False,
    storage: ZushStorage | None = None,
) -> tuple[list[tuple[Path, object, dict[str, Any]]], dict[str, Any]]:
    """Scan config.envs for packages matching env_prefix with __zush__.py;
    load plugins, merge command trees, update cache and sentry (unless no_cache).
    If mock_path is set, only that path is scanned (overload env). If no_cache is True,
    sentry/cache are not read or written. When storage is provided, read/write use it.
    Returns ([(package_path, instance, commands_dict), ...], merged_tree).
    """
    all_plugins: list[tuple[Path, object, dict[str, Any]]] = []
    merged_tree: dict[str, Any] = {}
    cached_tree = {} if no_cache else read_cache(storage=storage)
    sentry = [] if no_cache else read_sentry(storage=storage)
    cache_entries: list[dict[str, Any]] = []
    seen_envs: set[str] = set()

    if mock_path is not None:
        envs_to_scan = [Path(mock_path)]
    else:
        envs_to_scan: list[Path] = []
        # 1) playground (overloaded index env)
        if getattr(config, "playground", None) is not None and Path(config.playground).is_dir():
            envs_to_scan.append(Path(config.playground))
        # 2) optionally, current interpreter's site-packages
        if getattr(config, "include_current_env", False):
            envs_to_scan.extend(envs.current_site_package_dirs())
        # 3) explicit envs from config
        envs_to_scan.extend(config.envs)

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
                    _load_cached_plugins(cached_paths, all_plugins, merged_tree)
                continue
        try:
            mtime = env_path.stat().st_mtime
        except OSError:
            mtime = 0.0
        cache_entries.append({"env": env_str, "root": True, "last_cached": mtime})
        seen_envs.add(env_str)

        for child in env_path.iterdir():
            if not child.is_dir():
                continue
            if not any(child.name.startswith(p) for p in config.env_prefix):
                continue
            zush_file = child / "__zush__.py"
            if not zush_file.exists():
                continue
            try:
                instance, commands = load_plugin(child)
            except Exception:
                continue
            all_plugins.append((child, instance, commands))
            try:
                pkg_mtime = child.stat().st_mtime
            except OSError:
                pkg_mtime = 0.0
            cache_entries.append({
                "env": env_str,
                "root": False,
                "package": child.name,
                "last_cached": pkg_mtime,
            })
            _merge_commands_into_tree(merged_tree, commands, str(child.resolve()))

    if not no_cache and cache_entries:
        write_sentry(cache_entries, storage=storage)
        write_cache(merged_tree, storage=storage)
    return all_plugins, merged_tree


def _load_cached_plugins(
    package_paths: list[Path],
    all_plugins: list[tuple[Path, object, dict[str, Any]]],
    merged_tree: dict[str, Any],
) -> None:
    for package_path in package_paths:
        try:
            instance, commands = load_plugin(package_path)
        except Exception:
            continue
        all_plugins.append((package_path, instance, commands))
        _merge_commands_into_tree(merged_tree, commands, str(package_path.resolve()))


def _cached_package_paths_for_env(cached_tree: dict[str, Any], env_path: Path) -> list[Path]:
    env_root = env_path.resolve()
    package_paths: list[Path] = []
    seen: set[Path] = set()
    for package_path in _iter_cached_package_paths(cached_tree):
        if package_path.parent != env_root:
            continue
        if package_path in seen:
            continue
        seen.add(package_path)
        package_paths.append(package_path)
    return package_paths


def _iter_cached_package_paths(node: dict[str, Any]) -> list[Path]:
    package_paths: list[Path] = []
    for key, value in (node or {}).items():
        if key.startswith("_") or not isinstance(value, dict):
            continue
        raw_path = value.get("path")
        if isinstance(raw_path, str):
            try:
                package_paths.append(Path(raw_path).resolve())
            except OSError:
                pass
        children = value.get("children")
        if isinstance(children, dict):
            package_paths.extend(_iter_cached_package_paths(children))
    return package_paths


def _find_sentry_entry(
    sentry: list[dict[str, Any]], env: str, root: bool, package: str | None
) -> dict[str, Any] | None:
    for e in sentry:
        if e.get("env") != env or e.get("root") != root:
            continue
        if root and package is None:
            return e
        if not root and e.get("package") == package:
            return e
    return None


def _merge_commands_into_tree(tree: dict[str, Any], commands: dict[str, Any], package_path: str) -> None:
    """Merge dotted keys from commands into nested tree. Store path and exported names for cache."""
    for key in commands:
        parts = key.split(".")
        node = tree
        for part in parts[:-1]:
            if part not in node:
                node[part] = {"_zushtype": "path", "path": package_path, "exported": [], "children": {}}
            child = node[part]
            if isinstance(child, dict) and "_zushtype" in child:
                node = child.setdefault("children", {})
            else:
                node = child
        last = parts[-1]
        if last not in node:
            node[last] = {"_zushtype": "path", "path": package_path, "exported": [last]}
        elif isinstance(node.get(last), dict) and "_zushtype" in node[last]:
            node[last].setdefault("exported", []).append(last)
