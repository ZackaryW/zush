"""Plugin cron namespace synchronization helpers for onload registration and cleanup."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click
from croniter import croniter

from zush.cron.completion import normalize_day_change
from zush.cron.registry import read_cron_registry, resolve_command_target, write_cron_registry
from zush.discovery_provider import DiscoveryDiagnostic

if TYPE_CHECKING:
    from zush.core.storage import ZushStorage


def cron_plugin_state_file(storage: ZushStorage) -> Path:
    """Return the plugin-managed cron metadata path for the active storage target."""
    return storage.config_dir() / "cron_plugins.json"


def read_cron_plugin_state(storage: ZushStorage) -> dict[str, Any]:
    """Read plugin cron metadata and return a normalized mapping keyed by plugin name."""
    file_path = cron_plugin_state_file(storage)
    if not file_path.exists():
        return {"plugins": {}}
    try:
        with open(file_path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (json.JSONDecodeError, OSError):
        return {"plugins": {}}
    plugins = data.get("plugins") if isinstance(data, dict) else None
    return {"plugins": plugins if isinstance(plugins, dict) else {}}


def write_cron_plugin_state(data: dict[str, Any], storage: ZushStorage) -> None:
    """Write plugin cron metadata for namespace ownership and on-remove behavior."""
    plugins = data.get("plugins") if isinstance(data, dict) else None
    normalized = {"plugins": plugins if isinstance(plugins, dict) else {}}
    file_path = cron_plugin_state_file(storage)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as handle:
        json.dump(normalized, handle, indent=2)


def sync_plugin_cron_registry(
    root: click.Group,
    storage: ZushStorage,
    plugins: list[tuple[Path, object, dict[str, Any]]],
) -> list[DiscoveryDiagnostic]:
    """Synchronize plugin-declared cron namespaces on load and cleanup removed plugin namespaces."""
    diagnostics: list[DiscoveryDiagnostic] = []
    data = read_cron_registry(storage)
    state = read_cron_plugin_state(storage)
    state_plugins = state.get("plugins")
    if not isinstance(state_plugins, dict):
        state_plugins = {}
        state["plugins"] = state_plugins
    loaded_specs = _collect_plugin_cron_specs(plugins)
    loaded_names = {spec["plugin_name"] for spec in loaded_specs}
    changed = _cleanup_removed_plugin_namespaces(data, state_plugins, loaded_names)
    for spec in loaded_specs:
        plugin_name = spec["plugin_name"]
        namespace = spec["namespace"]
        register_mode = spec["register_mode"]
        on_conflict = spec["on_conflict"]
        on_remove = spec["on_remove"]
        previous_plugin_state = state_plugins.get(plugin_name)
        namespace_in_use = _namespace_in_use(data, namespace)
        already_owned = isinstance(previous_plugin_state, dict) and previous_plugin_state.get("namespace") == namespace
        if namespace_in_use and not already_owned and on_conflict == "skip":
            diagnostics.append(
                DiscoveryDiagnostic(
                    source="cron",
                    code="cron-namespace-conflict",
                    message=f"Skipped plugin cron namespace '{namespace}' due to existing entries",
                    extension_key=plugin_name,
                )
            )
            state_plugins[plugin_name] = {
                "namespace": namespace,
                "register_mode": register_mode,
                "on_conflict": on_conflict,
                "on_remove": on_remove,
            }
            continue
        if register_mode == "once" and _namespace_in_use(data, namespace):
            state_plugins[plugin_name] = {
                "namespace": namespace,
                "register_mode": register_mode,
                "on_conflict": on_conflict,
                "on_remove": on_remove,
            }
            continue
        try:
            if register_mode == "reinforce":
                _remove_namespace_entries(data, namespace)
                changed = True
            _apply_plugin_cron_spec(root, data, spec)
            changed = True
            state_plugins[plugin_name] = {
                "namespace": namespace,
                "register_mode": register_mode,
                "on_conflict": on_conflict,
                "on_remove": on_remove,
            }
        except click.ClickException as exc:
            diagnostics.append(
                DiscoveryDiagnostic(
                    source="cron",
                    code="cron-plugin-sync-failed",
                    message=str(exc),
                    extension_key=plugin_name,
                )
            )
    if changed:
        write_cron_registry(data, storage)
    write_cron_plugin_state(state, storage)
    return diagnostics


def _collect_plugin_cron_specs(plugins: list[tuple[Path, object, dict[str, Any]]]) -> list[dict[str, Any]]:
    """Extract plugin cron declarations from loaded plugin instances for synchronization."""
    specs: list[dict[str, Any]] = []
    for path, instance, _commands in plugins:
        config = getattr(instance, "cron_namespace_config", None)
        if not isinstance(config, dict):
            continue
        namespace = config.get("namespace")
        if not isinstance(namespace, str) or not namespace:
            continue
        registrations = getattr(instance, "cron_registrations", [])
        jobs = getattr(instance, "cron_jobs", [])
        lifejobs = getattr(instance, "cron_lifejobs", [])
        specs.append(
            {
                "plugin_name": str(path.name),
                "namespace": namespace,
                "register_mode": str(config.get("register_mode") or "once"),
                "on_conflict": str(config.get("on_conflict") or "skip"),
                "on_remove": str(config.get("on_remove") or "keep"),
                "registrations": registrations if isinstance(registrations, list) else [],
                "jobs": jobs if isinstance(jobs, list) else [],
                "lifejobs": lifejobs if isinstance(lifejobs, list) else [],
            }
        )
    return specs


def _cleanup_removed_plugin_namespaces(
    data: dict[str, Any],
    state_plugins: dict[str, Any],
    loaded_names: set[str],
) -> bool:
    """Remove namespace entries for plugins no longer loaded when their policy requires unregistering."""
    changed = False
    for plugin_name in list(state_plugins.keys()):
        if plugin_name in loaded_names:
            continue
        metadata = state_plugins.get(plugin_name)
        namespace = metadata.get("namespace") if isinstance(metadata, dict) else None
        on_remove = metadata.get("on_remove") if isinstance(metadata, dict) else None
        if isinstance(namespace, str) and namespace and on_remove == "unregister":
            if _remove_namespace_entries(data, namespace):
                changed = True
        del state_plugins[plugin_name]
        changed = True
    return changed


def _namespace_in_use(data: dict[str, Any], namespace: str) -> bool:
    """Return whether any cron registration, job, or lifejob uses the namespace prefix."""
    prefix = f"{namespace}."
    for bucket_name in ("registrations", "jobs", "lifejobs"):
        bucket = data.get(bucket_name)
        if not isinstance(bucket, dict):
            continue
        for key in bucket.keys():
            if isinstance(key, str) and key.startswith(prefix):
                return True
    return False


def _remove_namespace_entries(data: dict[str, Any], namespace: str) -> bool:
    """Remove all cron registration, job, and lifejob entries for one namespace prefix."""
    prefix = f"{namespace}."
    changed = False
    for bucket_name in ("registrations", "jobs", "lifejobs"):
        bucket = data.get(bucket_name)
        if not isinstance(bucket, dict):
            continue
        for key in [name for name in bucket.keys() if isinstance(name, str) and name.startswith(prefix)]:
            del bucket[key]
            changed = True
    return changed


def _namespaced_name(namespace: str, name: str) -> str:
    """Compose one fully qualified cron entry name inside the given namespace."""
    return f"{namespace}.{name}"


def _apply_plugin_cron_spec(root: click.Group, data: dict[str, Any], spec: dict[str, Any]) -> None:
    """Apply one plugin cron declaration set into the in-memory cron registry."""
    namespace = str(spec["namespace"])
    registrations = data.setdefault("registrations", {})
    jobs = data.setdefault("jobs", {})
    lifejobs = data.setdefault("lifejobs", {})
    if not isinstance(registrations, dict) or not isinstance(jobs, dict) or not isinstance(lifejobs, dict):
        raise click.ClickException("Cron registry is malformed")

    for item in spec["registrations"]:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        command_path = item.get("command")
        if not isinstance(name, str) or not isinstance(command_path, str):
            continue
        resolve_command_target(root, command_path)
        registrations[_namespaced_name(namespace, name)] = {
            "command": command_path,
            "args": list(item.get("args") or []),
            "kwargs": dict(item.get("kwargs") or {}),
            "detach": bool(item.get("detach", False)),
        }

    for item in spec["jobs"]:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        schedule = item.get("schedule")
        registration = item.get("registration")
        if not isinstance(name, str) or not isinstance(schedule, str) or not isinstance(registration, str):
            continue
        croniter(schedule)
        payload: dict[str, Any] = {
            "schedule": schedule,
            "target": _namespaced_name(namespace, registration),
            "last_run_at": None,
        }
        if bool(item.get("single_day_complete", False)):
            payload["single_day_complete"] = True
        day_change = item.get("day_change")
        if isinstance(day_change, str):
            payload["day_change"] = normalize_day_change(day_change)
        jobs[_namespaced_name(namespace, name)] = payload

    for item in spec["lifejobs"]:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        registration = item.get("registration")
        target_job = item.get("target_job")
        delay_seconds = item.get("delay_seconds")
        if (
            not isinstance(name, str)
            or not isinstance(registration, str)
            or not isinstance(target_job, str)
            or not isinstance(delay_seconds, int)
        ):
            continue
        if delay_seconds < 0:
            raise click.ClickException("Lifejob delay must be a non-negative integer")
        payload: dict[str, Any] = {
            "target": _namespaced_name(namespace, registration),
            "target_job": _namespaced_name(namespace, target_job),
            "delay_seconds": delay_seconds,
            "pending_due_at": None,
            "last_run_at": None,
        }
        if bool(item.get("single_day_complete", False)):
            payload["single_day_complete"] = True
        day_change = item.get("day_change")
        if isinstance(day_change, str):
            payload["day_change"] = normalize_day_change(day_change)
        lifejobs[_namespaced_name(namespace, name)] = payload
