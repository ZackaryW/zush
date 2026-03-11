"""Scan envs for plugins; load and merge command trees; update cache and sentry."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from zush import paths
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
    sentry = [] if no_cache else read_sentry(storage=storage)
    cache_entries: list[dict[str, Any]] = []
    seen_envs: set[str] = set()

    if mock_path is not None:
        envs_to_scan = [Path(mock_path)]
    else:
        envs_to_scan = []
        if getattr(config, "playground", None) is not None and Path(config.playground).is_dir():
            envs_to_scan.append(Path(config.playground))
        envs_to_scan.extend(config.envs)

    for env_path in envs_to_scan:
        env_path = Path(env_path)
        if not env_path.is_dir():
            continue
        env_str = str(env_path.resolve())
        if not no_cache:
            sentry_entry = _find_sentry_entry(sentry, env_str, root=True, package=None)
            if not is_env_stale(env_path, sentry_entry):
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
