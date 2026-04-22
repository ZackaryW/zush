"""Cron registry helpers and CRUD operations for built-in and plugin-managed entries."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click
from croniter import croniter

from zush.cron.completion import normalize_day_change

if TYPE_CHECKING:
    from zush.core.storage import ZushStorage


def cron_file(storage: ZushStorage) -> Path:
    """Return the base-folder cron registry path for the active storage target."""
    return storage.config_dir() / "cron.json"


def cron_created_at() -> str:
    """Return a stable ISO timestamp for newly created cron jobs and lifejobs."""
    return datetime.now().replace(microsecond=0).isoformat(timespec="seconds")


def empty_cron_registry() -> dict[str, Any]:
    """Return the canonical empty cron registry shape."""
    return {"registrations": {}, "jobs": {}, "lifejobs": {}}


def normalize_cron_registry(data: Any) -> dict[str, Any]:
    """Return one normalized cron registry with registration and job maps."""
    if not isinstance(data, dict):
        return empty_cron_registry()
    registrations = data.get("registrations")
    jobs = data.get("jobs")
    lifejobs = data.get("lifejobs")
    return {
        "registrations": registrations if isinstance(registrations, dict) else {},
        "jobs": jobs if isinstance(jobs, dict) else {},
        "lifejobs": lifejobs if isinstance(lifejobs, dict) else {},
    }


def read_cron_registry(storage: ZushStorage) -> dict[str, Any]:
    """Read cron.json and return a normalized registry shape when missing or invalid."""
    file_path = cron_file(storage)
    if not file_path.exists():
        return empty_cron_registry()
    try:
        with open(file_path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (json.JSONDecodeError, OSError):
        return empty_cron_registry()
    return normalize_cron_registry(data)


def write_cron_registry(data: dict[str, Any], storage: ZushStorage) -> None:
    """Write cron.json under the active base folder, creating the directory when needed."""
    file_path = cron_file(storage)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as handle:
        json.dump(normalize_cron_registry(data), handle, indent=2)


def resolve_command_target(root: click.Group, command_path: str) -> click.Command:
    """Resolve one dotted command path against the live root tree and require a concrete command."""
    current: click.Command = root
    for part in [segment for segment in command_path.split(".") if segment]:
        if not isinstance(current, click.Group):
            raise click.ClickException(f"Command path '{command_path}' stops before '{part}'")
        next_command = current.commands.get(part)
        if next_command is None:
            raise click.ClickException(f"Unknown command path '{command_path}'")
        current = next_command
    if isinstance(current, click.Group):
        raise click.ClickException(f"Command path '{command_path}' must resolve to a command")
    return current


def split_cli_tokens(raw_tokens: list[str]) -> tuple[list[str], dict[str, str]]:
    """Split raw cron command tokens into positional args and key=value kwargs."""
    args: list[str] = []
    kwargs: dict[str, str] = {}
    for token in raw_tokens:
        if token.startswith("-") or "=" not in token:
            args.append(token)
            continue
        key, value = token.split("=", 1)
        if not key:
            args.append(token)
            continue
        kwargs[key] = value
    return args, kwargs


def next_cron_name(data: dict[str, Any]) -> str:
    """Return the next default cron name using the highest existing cron-N suffix plus one."""
    jobs = data.get("jobs")
    if not isinstance(jobs, dict):
        return "cron-1"
    highest = 0
    for name in jobs:
        if not isinstance(name, str) or not name.startswith("cron-"):
            continue
        try:
            highest = max(highest, int(name.split("-", 1)[1]))
        except ValueError:
            continue
    return f"cron-{highest + 1}"


def next_lifejob_name(data: dict[str, Any]) -> str:
    """Return the next default lifejob name using the highest existing lifejob-N suffix plus one."""
    lifejobs = data.get("lifejobs")
    if not isinstance(lifejobs, dict):
        return "lifejob-1"
    highest = 0
    for name in lifejobs:
        if not isinstance(name, str) or not name.startswith("lifejob-"):
            continue
        try:
            highest = max(highest, int(name.split("-", 1)[1]))
        except ValueError:
            continue
    return f"lifejob-{highest + 1}"


def _resolve_registered_target(
    data: dict[str, Any],
    registration_name: str,
    owner_label: str,
) -> dict[str, Any]:
    """Resolve one named registration and require it to exist for the owning cron entry."""
    registrations = data.get("registrations")
    if not isinstance(registrations, dict):
        raise click.ClickException(f"Unknown cron registration '{registration_name}' referenced by {owner_label}")
    registration = registrations.get(registration_name)
    if not isinstance(registration, dict):
        raise click.ClickException(f"Unknown cron registration '{registration_name}' referenced by {owner_label}")
    return registration


def resolve_cron_registration(
    data: dict[str, Any],
    job_name: str,
    job: dict[str, Any],
) -> tuple[str | None, dict[str, Any]]:
    """Resolve one job to a reusable registration or a legacy inline command payload."""
    registrations = data.get("registrations")
    if not isinstance(registrations, dict):
        registrations = {}
    target_name = job.get("target")
    if isinstance(target_name, str) and target_name:
        registration = registrations.get(target_name)
        if not isinstance(registration, dict):
            raise click.ClickException(
                f"Cron registration '{target_name}' referenced by job '{job_name}' does not exist"
            )
        return target_name, registration
    command_path = job.get("command")
    if not isinstance(command_path, str) or not command_path:
        raise click.ClickException(f"Cron job '{job_name}' is missing a registration target")
    args = job.get("args") if isinstance(job.get("args"), list) else []
    kwargs = job.get("kwargs") if isinstance(job.get("kwargs"), dict) else {}
    return None, {
        "command": command_path,
        "args": args,
        "kwargs": kwargs,
        "detach": bool(job.get("detach", False)),
    }


def register_cron_command(
    root: click.Group,
    storage: ZushStorage,
    name: str,
    command_path: str,
    raw_tokens: list[str],
    detach: bool = False,
) -> str:
    """Persist one reusable cron command registration for a live dotted command path."""
    resolve_command_target(root, command_path)
    data = read_cron_registry(storage)
    args, kwargs = split_cli_tokens(raw_tokens)
    registrations = data.setdefault("registrations", {})
    if not isinstance(registrations, dict):
        registrations = {}
        data["registrations"] = registrations
    if name in registrations:
        raise click.ClickException(f"Cron registration '{name}' already exists")
    registrations[name] = {
        "command": command_path,
        "args": args,
        "kwargs": kwargs,
        "detach": bool(detach),
    }
    write_cron_registry(data, storage)
    return name


def add_cron_lifejob(
    storage: ZushStorage,
    registration_name: str,
    target_job_name: str,
    delay_seconds: int,
    single_day_complete: bool = False,
    day_change: str | None = None,
    name: str | None = None,
) -> str:
    """Persist one delayed follower lifejob that runs after a target cron job completes."""
    if delay_seconds < 0:
        raise click.ClickException("Lifejob delay must be a non-negative integer")
    data = read_cron_registry(storage)
    jobs = data.get("jobs")
    if not isinstance(jobs, dict) or target_job_name not in jobs:
        raise click.ClickException(f"Unknown cron job '{target_job_name}'")
    _resolve_registered_target(data, registration_name, f"lifejob '{name or 'new lifejob'}'")
    resolved_name = name or next_lifejob_name(data)
    lifejobs = data.setdefault("lifejobs", {})
    if not isinstance(lifejobs, dict):
        lifejobs = {}
        data["lifejobs"] = lifejobs
    if resolved_name in lifejobs:
        raise click.ClickException(f"Lifejob '{resolved_name}' already exists")
    normalized_day_change = normalize_day_change(day_change) if day_change is not None else None
    lifejob_payload: dict[str, Any] = {
        "target": registration_name,
        "target_job": target_job_name,
        "delay_seconds": int(delay_seconds),
        "pending_due_at": None,
        "last_run_at": None,
        "created_at": cron_created_at(),
    }
    if single_day_complete:
        lifejob_payload["single_day_complete"] = True
    if normalized_day_change is not None:
        lifejob_payload["day_change"] = normalized_day_change
    lifejobs[resolved_name] = lifejob_payload
    write_cron_registry(data, storage)
    return resolved_name


def add_cron_job(
    storage: ZushStorage,
    registration_name: str,
    schedule: str,
    single_day_complete: bool = False,
    day_change: str | None = None,
    name: str | None = None,
) -> str:
    """Persist one cron schedule entry that targets an existing command registration."""
    croniter(schedule)
    data = read_cron_registry(storage)
    registrations = data.get("registrations")
    if not isinstance(registrations, dict) or registration_name not in registrations:
        raise click.ClickException(f"Unknown cron registration '{registration_name}'")
    resolved_name = name or next_cron_name(data)
    jobs = data.setdefault("jobs", {})
    if not isinstance(jobs, dict):
        jobs = {}
        data["jobs"] = jobs
    if resolved_name in jobs:
        raise click.ClickException(f"Cron job '{resolved_name}' already exists")
    normalized_day_change = normalize_day_change(day_change) if day_change is not None else None
    job_payload: dict[str, Any] = {
        "schedule": schedule,
        "target": registration_name,
        "last_run_at": None,
        "created_at": cron_created_at(),
    }
    if single_day_complete:
        job_payload["single_day_complete"] = True
    if normalized_day_change is not None:
        job_payload["day_change"] = normalized_day_change
    jobs[resolved_name] = job_payload
    write_cron_registry(data, storage)
    return resolved_name


def list_cron_registrations(storage: ZushStorage) -> list[tuple[str, dict[str, Any]]]:
    """Return persisted cron command registrations sorted by name."""
    data = read_cron_registry(storage)
    registrations = data.get("registrations")
    if not isinstance(registrations, dict):
        return []
    entries: list[tuple[str, dict[str, Any]]] = []
    for name in sorted(registrations.keys()):
        registration = registrations.get(name)
        if isinstance(name, str) and isinstance(registration, dict):
            entries.append((name, registration))
    return entries


def list_cron_jobs(storage: ZushStorage) -> list[tuple[str, dict[str, Any]]]:
    """Return persisted cron jobs sorted by name for the active base folder."""
    data = read_cron_registry(storage)
    jobs = data.get("jobs")
    if not isinstance(jobs, dict):
        return []
    entries: list[tuple[str, dict[str, Any]]] = []
    for name in sorted(jobs.keys()):
        job = jobs.get(name)
        if isinstance(name, str) and isinstance(job, dict):
            entries.append((name, job))
    return entries


def list_cron_lifejobs(storage: ZushStorage) -> list[tuple[str, dict[str, Any]]]:
    """Return persisted lifejobs sorted by name for the active base folder."""
    data = read_cron_registry(storage)
    lifejobs = data.get("lifejobs")
    if not isinstance(lifejobs, dict):
        return []
    entries: list[tuple[str, dict[str, Any]]] = []
    for name in sorted(lifejobs.keys()):
        lifejob = lifejobs.get(name)
        if isinstance(name, str) and isinstance(lifejob, dict):
            entries.append((name, lifejob))
    return entries


def unregister_cron_command(storage: ZushStorage, registration_name: str) -> None:
    """Remove one persisted cron command registration when no jobs still reference it."""
    data = read_cron_registry(storage)
    registrations = data.get("registrations")
    jobs = data.get("jobs")
    lifejobs = data.get("lifejobs")
    if not isinstance(registrations, dict) or registration_name not in registrations:
        raise click.ClickException(f"Unknown cron registration '{registration_name}'")
    if isinstance(jobs, dict):
        for job_name, job in jobs.items():
            if isinstance(job_name, str) and isinstance(job, dict) and job.get("target") == registration_name:
                raise click.ClickException(
                    f"Cron registration '{registration_name}' is still used by job '{job_name}'"
                )
    if isinstance(lifejobs, dict):
        for lifejob_name, lifejob in lifejobs.items():
            if isinstance(lifejob_name, str) and isinstance(lifejob, dict) and lifejob.get("target") == registration_name:
                raise click.ClickException(
                    f"Cron registration '{registration_name}' is still used by lifejob '{lifejob_name}'"
                )
    del registrations[registration_name]
    write_cron_registry(data, storage)


def remove_cron_job(storage: ZushStorage, job_name: str) -> None:
    """Remove one persisted cron job from the active base folder registry."""
    data = read_cron_registry(storage)
    jobs = data.get("jobs")
    lifejobs = data.get("lifejobs")
    if not isinstance(jobs, dict) or job_name not in jobs:
        raise click.ClickException(f"Unknown cron job '{job_name}'")
    del jobs[job_name]
    if isinstance(lifejobs, dict):
        for lifejob_name in [
            name
            for name, lifejob in lifejobs.items()
            if isinstance(name, str) and isinstance(lifejob, dict) and lifejob.get("target_job") == job_name
        ]:
            del lifejobs[lifejob_name]
    write_cron_registry(data, storage)
