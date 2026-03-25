from __future__ import annotations

from pathlib import Path
from typing import Any

from zush.config import Config
from zush.plugin_loader import load_plugin


def build_envs_to_scan(
    config: Config,
    mock_path: Path | None = None,
    current_site_package_dirs=None,
) -> list[Path]:
    if mock_path is not None:
        return [Path(mock_path)]

    envs_to_scan: list[Path] = []
    playground = getattr(config, "playground", None)
    if playground is not None and playground.is_dir():
        envs_to_scan.append(playground)
    if getattr(config, "include_current_env", False):
        site_dirs = current_site_package_dirs() if current_site_package_dirs is not None else []
        envs_to_scan.extend(site_dirs)
    envs_to_scan.extend(config.envs)
    return envs_to_scan


def scan_env_for_plugins(
    env_path: Path,
    env_prefixes: list[str],
    all_plugins: list[tuple[Path, object, dict[str, Any]]],
    merged_tree: dict[str, Any],
    cache_entries: list[dict[str, Any]],
    merge_commands_into_tree,
) -> None:
    env_str = str(env_path.resolve())
    try:
        mtime = env_path.stat().st_mtime
    except OSError:
        mtime = 0.0
    cache_entries.append({"env": env_str, "root": True, "last_cached": mtime})

    for child in env_path.iterdir():
        if not child.is_dir():
            continue
        if not any(child.name.startswith(prefix) for prefix in env_prefixes):
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
        merge_commands_into_tree(merged_tree, commands, str(child.resolve()))


def load_cached_plugins(
    package_paths: list[Path],
    all_plugins: list[tuple[Path, object, dict[str, Any]]],
    merged_tree: dict[str, Any],
    merge_commands_into_tree,
) -> None:
    for package_path in package_paths:
        try:
            instance, commands = load_plugin(package_path)
        except Exception:
            continue
        all_plugins.append((package_path, instance, commands))
        merge_commands_into_tree(merged_tree, commands, str(package_path.resolve()))


def cached_package_paths_for_env(cached_tree: dict[str, Any], env_path: Path) -> list[Path]:
    env_root = env_path.resolve()
    package_paths: list[Path] = []
    seen: set[Path] = set()
    for package_path in iter_cached_package_paths(cached_tree):
        if package_path.parent != env_root:
            continue
        if package_path in seen:
            continue
        seen.add(package_path)
        package_paths.append(package_path)
    return package_paths


def iter_cached_package_paths(node: dict[str, Any]) -> list[Path]:
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
            package_paths.extend(iter_cached_package_paths(children))
    return package_paths


def find_sentry_entry(
    sentry: list[dict[str, Any]], env: str, root: bool, package: str | None
) -> dict[str, Any] | None:
    for entry in sentry:
        if entry.get("env") != env or entry.get("root") != root:
            continue
        if root and package is None:
            return entry
        if not root and entry.get("package") == package:
            return entry
    return None


def merge_commands_into_tree(tree: dict[str, Any], commands: dict[str, Any], package_path: str) -> None:
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
