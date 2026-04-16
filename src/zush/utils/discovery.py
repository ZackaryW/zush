from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from zush.configparse.config import Config
from zush.discovery_provider import (
    DiscoveryCandidate,
    DiscoveryDiagnostic,
    DiscoveryReport,
    FlatFolderDiscoveryProvider,
)
from zush.pluginloader.loader import load_plugin

if TYPE_CHECKING:
    from zush.discovery_provider import DiscoveryProvider


def normalize_providers(provider: DiscoveryProvider | list[DiscoveryProvider] | tuple[DiscoveryProvider, ...] | None) -> list[DiscoveryProvider]:
    """Return an ordered provider list while preserving the default flat-folder behavior."""
    if provider is None:
        return [FlatFolderDiscoveryProvider()]
    if isinstance(provider, list | tuple):
        return list(provider)
    return [provider]


def build_envs_to_scan(
    config: Config,
    mock_path: Path | None = None,
    current_site_package_dirs=None,
) -> list[Path]:
    """Return the ordered list of env roots that discovery should scan for plugins."""
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


def resolve_extension_key(package_path: Path) -> str:
    """Return the current extension key for a discovered package path.

    The current flat-folder discovery flow uses the package directory name as
    the stable extension key, which matches the import/module name.
    """
    return package_path.name


def scan_env_for_plugins(
    env_path: Path,
    env_prefixes: list[str],
    all_plugins: list[tuple[Path, object, dict[str, Any]]],
    merged_tree: dict[str, Any],
    cache_entries: list[dict[str, Any]],
    merge_commands_into_tree,
    disabled_extensions: set[str] | None = None,
    provider: DiscoveryProvider | list[DiscoveryProvider] | tuple[DiscoveryProvider, ...] | None = None,
    diagnostics: list[DiscoveryDiagnostic] | None = None,
) -> None:
    """Scan one env root, loading only enabled plugin packages and cache metadata."""
    env_str = str(env_path.resolve())
    try:
        mtime = env_path.stat().st_mtime
    except OSError:
        mtime = 0.0
    cache_entries.append({"env": env_str, "root": True, "last_cached": mtime})

    report = _provider_report(
        normalize_providers(provider),
        env_path,
        env_prefixes,
        disabled_extensions=disabled_extensions,
    )
    if diagnostics is not None:
        diagnostics.extend(report.diagnostics)
    for candidate in report.candidates:
        child = candidate.package_path
        try:
            instance, commands = load_plugin(child)
        except Exception as exc:
            if diagnostics is not None:
                diagnostics.append(
                    DiscoveryDiagnostic(
                        source="loader",
                        code="plugin-load-failed",
                        message=str(exc),
                        env_path=env_path,
                        package_path=child,
                        extension_key=candidate.extension_key,
                    )
                )
            continue
        all_plugins.append((child, instance, commands))
        try:
            pkg_mtime = child.stat().st_mtime
        except OSError:
            pkg_mtime = 0.0
        cache_entries.append({
            "env": env_str,
            "root": False,
            "package": candidate.extension_key,
            "last_cached": pkg_mtime,
        })
        merge_commands_into_tree(merged_tree, commands, str(child.resolve()))


def load_cached_plugins(
    package_paths: list[Path],
    all_plugins: list[tuple[Path, object, dict[str, Any]]],
    merged_tree: dict[str, Any],
    merge_commands_into_tree,
    disabled_extensions: set[str] | None = None,
    diagnostics: list[DiscoveryDiagnostic] | None = None,
) -> None:
    """Reload enabled plugins from cached package paths for an unchanged env."""
    for package_path in package_paths:
        if resolve_extension_key(package_path) in (disabled_extensions or set()):
            continue
        try:
            instance, commands = load_plugin(package_path)
        except Exception as exc:
            if diagnostics is not None:
                diagnostics.append(
                    DiscoveryDiagnostic(
                        source="loader",
                        code="plugin-load-failed",
                        message=str(exc),
                        package_path=package_path,
                        extension_key=resolve_extension_key(package_path),
                    )
                )
            continue
        all_plugins.append((package_path, instance, commands))
        merge_commands_into_tree(merged_tree, commands, str(package_path.resolve()))


def _provider_report(
    providers: list[DiscoveryProvider],
    env_path: Path,
    env_prefixes: list[str],
    disabled_extensions: set[str] | None = None,
) -> DiscoveryReport:
    """Select the first matching provider for one env path and normalize its output."""
    for provider in providers:
        identify = getattr(provider, "identify", None)
        if callable(identify) and not identify(env_path, env_prefixes):
            continue
        discover = getattr(provider, "discover", None)
        if callable(discover):
            return discover(env_path, env_prefixes, disabled_extensions=disabled_extensions)
        discover_candidates = getattr(provider, "discover_candidates", None)
        if callable(discover_candidates):
            candidates = discover_candidates(env_path, env_prefixes, disabled_extensions=disabled_extensions)
            return DiscoveryReport(candidates=list(candidates), diagnostics=[])
    return DiscoveryReport(
        candidates=[],
        diagnostics=[
            DiscoveryDiagnostic(
                source="provider",
                code="no-provider-matched",
                message="No discovery provider identified the env path",
                env_path=env_path,
            )
        ],
    )


def cached_package_paths_for_env(cached_tree: dict[str, Any], env_path: Path) -> list[Path]:
    """Return cached package paths that belong directly to one env root."""
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
    """Walk a cached tree payload and collect package paths from path nodes."""
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
    """Find the sentry entry matching one env root or child package."""
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
