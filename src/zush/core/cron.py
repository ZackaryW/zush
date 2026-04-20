"""Cron registry helpers and scheduler entrypoints for built-in self cron commands."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click
from croniter import croniter
from zush.core.cron_completion import has_single_day_completion, mark_single_day_completion, normalize_day_change

if TYPE_CHECKING:
    from zush.core.storage import ZushStorage


def cron_file(storage: ZushStorage) -> Path:
    """Return the base-folder cron registry path for the active storage target."""
    return storage.config_dir() / "cron.json"


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


def _iso_timestamp(value: datetime) -> str:
    """Return one stable second-resolution ISO timestamp for cron state persistence."""
    return value.replace(microsecond=0).isoformat(timespec="seconds")


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
    lifejob_payload = {
        "target": registration_name,
        "target_job": target_job_name,
        "delay_seconds": int(delay_seconds),
        "pending_due_at": None,
        "last_run_at": None,
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
    job_payload = {
        "schedule": schedule,
        "target": registration_name,
        "last_run_at": None,
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


def start_cron_scheduler(root: click.Group, storage: ZushStorage) -> None:
    """Run the foreground cron scheduler loop for the active root command tree and storage target."""
    while True:
        run_due_cron_jobs(root, storage)
        time.sleep(1.0)


def run_due_cron_jobs(root: click.Group, storage: ZushStorage, now: datetime | None = None) -> list[str]:
    """Run every due cron entry for the given time and return any emitted scheduler events."""
    current_time = now or datetime.now()
    data = read_cron_registry(storage)
    changed, events = process_due_cron_registry(root, storage, data, current_time)
    if changed:
        write_cron_registry(data, storage)
    return events


def process_due_cron_registry(
    root: click.Group,
    storage: ZushStorage,
    data: dict[str, Any],
    current_time: datetime,
    dry_run: bool = False,
) -> tuple[bool, list[str]]:
    """Process one in-memory cron registry snapshot for the given time and optionally skip execution."""
    current_slot = current_time.replace(second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M")
    jobs = data.get("jobs")
    if not isinstance(jobs, dict):
        jobs = {}
    changed = False
    events: list[str] = []
    for name, job in jobs.items():
        if not isinstance(name, str) or not isinstance(job, dict):
            continue
        schedule = job.get("schedule")
        last_run_at = job.get("last_run_at")
        if not isinstance(schedule, str) or not schedule:
            continue
        if last_run_at == current_slot:
            continue
        try:
            should_run = bool(croniter.match(schedule, current_time))
        except (ValueError, KeyError):
            continue
        if not should_run:
            continue
        try:
            _, registration = resolve_cron_registration(data, name, job)
        except click.ClickException:
            continue
        day_change = str(job.get("day_change")) if isinstance(job.get("day_change"), str) else None
        if bool(job.get("single_day_complete", False)) and has_single_day_completion(
            storage,
            name,
            current_time,
            day_change,
        ):
            continue
        if dry_run:
            events.append(_describe_dispatch("job", name, registration, current_time))
        elif bool(registration.get("detach", False)):
            spawn_detached_cron_job(storage, name)
        else:
            invoke_cron_job(root, storage, name)
        if bool(job.get("single_day_complete", False)) and not dry_run:
            mark_single_day_completion(storage, name, current_time, day_change)
        job["last_run_at"] = current_slot
        _schedule_attached_lifejobs(data, target_job_name=name, current_time=current_time)
        changed = True
    lifejob_changed, lifejob_events = _run_due_lifejobs(
        root,
        storage,
        data,
        current_time=current_time,
        dry_run=dry_run,
    )
    if lifejob_changed:
        changed = True
    events.extend(lifejob_events)
    return changed, events


def invoke_cron_job(root: click.Group, storage: ZushStorage, job_name: str) -> None:
    """Execute one persisted cron job in-process through the live Click command tree."""
    data = read_cron_registry(storage)
    jobs = data.get("jobs")
    if not isinstance(jobs, dict):
        raise click.ClickException(f"Unknown cron job '{job_name}'")
    job = jobs.get(job_name)
    if not isinstance(job, dict):
        raise click.ClickException(f"Unknown cron job '{job_name}'")
    _, registration = resolve_cron_registration(data, job_name, job)
    _invoke_registered_command(root, registration, job_name)


def invoke_lifejob(root: click.Group, storage: ZushStorage, lifejob_name: str) -> None:
    """Execute one persisted lifejob in-process through the live Click command tree."""
    data = read_cron_registry(storage)
    lifejobs = data.get("lifejobs")
    if not isinstance(lifejobs, dict):
        raise click.ClickException(f"Unknown lifejob '{lifejob_name}'")
    lifejob = lifejobs.get(lifejob_name)
    if not isinstance(lifejob, dict):
        raise click.ClickException(f"Unknown lifejob '{lifejob_name}'")
    target_job_name = lifejob.get("target_job")
    jobs = data.get("jobs")
    if not isinstance(target_job_name, str) or not isinstance(jobs, dict) or target_job_name not in jobs:
        raise click.ClickException(f"Lifejob '{lifejob_name}' references unknown cron job '{target_job_name}'")
    registration_name = lifejob.get("target")
    if not isinstance(registration_name, str) or not registration_name:
        raise click.ClickException(f"Lifejob '{lifejob_name}' is missing a registration target")
    registration = _resolve_registered_target(data, registration_name, f"lifejob '{lifejob_name}'")
    _invoke_registered_command(root, registration, lifejob_name)


def _invoke_registered_command(root: click.Group, registration: dict[str, Any], owner_name: str) -> None:
    """Invoke one resolved registration payload through the live Click command tree."""
    command_path = registration.get("command")
    args = registration.get("args")
    kwargs = registration.get("kwargs")
    if not isinstance(command_path, str) or not command_path:
        raise click.ClickException(f"Cron entry '{owner_name}' is missing a command path")
    command, context = build_command_context(root, command_path)
    callback = getattr(command, "callback", None)
    if not callable(callback):
        raise click.ClickException(f"Command path '{command_path}' is not executable")
    positional_args = [str(value) for value in args] if isinstance(args, list) else []
    keyword_args = {str(key): value for key, value in kwargs.items()} if isinstance(kwargs, dict) else {}
    _invoke_callback(root, command_path, context, callback, positional_args, keyword_args)


def _describe_dispatch(
    entry_kind: str,
    entry_name: str,
    registration: dict[str, Any],
    current_time: datetime,
) -> str:
    """Return one human-readable dry-run dispatch line for a due cron or lifejob entry."""
    command_path = str(registration.get("command") or "")
    return f"dry-run {entry_kind} {entry_name} at {_iso_timestamp(current_time)} -> {command_path}"


def _schedule_attached_lifejobs(data: dict[str, Any], target_job_name: str, current_time: datetime) -> None:
    """Reschedule each lifejob attached to the completed target job from the latest run timestamp."""
    lifejobs = data.get("lifejobs")
    if not isinstance(lifejobs, dict):
        return
    for lifejob in lifejobs.values():
        if not isinstance(lifejob, dict) or lifejob.get("target_job") != target_job_name:
            continue
        delay_seconds = lifejob.get("delay_seconds")
        if not isinstance(delay_seconds, int) or delay_seconds < 0:
            continue
        lifejob["pending_due_at"] = _iso_timestamp(current_time + timedelta(seconds=delay_seconds))


def _run_due_lifejobs(
    root: click.Group,
    storage: ZushStorage,
    data: dict[str, Any],
    current_time: datetime,
    dry_run: bool = False,
) -> tuple[bool, list[str]]:
    """Run each pending lifejob whose delay has elapsed and return any emitted scheduler events."""
    lifejobs = data.get("lifejobs")
    jobs = data.get("jobs")
    if not isinstance(lifejobs, dict):
        return False, []
    changed = False
    events: list[str] = []
    for name, lifejob in lifejobs.items():
        if not isinstance(name, str) or not isinstance(lifejob, dict):
            continue
        target_job_name = lifejob.get("target_job")
        if not isinstance(target_job_name, str) or not isinstance(jobs, dict) or target_job_name not in jobs:
            continue
        pending_due_at = lifejob.get("pending_due_at")
        if not isinstance(pending_due_at, str) or not pending_due_at:
            continue
        try:
            due_time = datetime.fromisoformat(pending_due_at)
        except ValueError:
            continue
        if due_time > current_time:
            continue
        registration_name = lifejob.get("target")
        if not isinstance(registration_name, str) or not registration_name:
            continue
        try:
            registration = _resolve_registered_target(data, registration_name, f"lifejob '{name}'")
        except click.ClickException:
            continue
        day_change = str(lifejob.get("day_change")) if isinstance(lifejob.get("day_change"), str) else None
        if bool(lifejob.get("single_day_complete", False)) and has_single_day_completion(
            storage,
            name,
            current_time,
            day_change,
        ):
            lifejob["pending_due_at"] = None
            changed = True
            continue
        if dry_run:
            events.append(_describe_dispatch("lifejob", name, registration, current_time))
        elif bool(registration.get("detach", False)):
            spawn_detached_lifejob(storage, name)
        else:
            invoke_lifejob(root, storage, name)
        if bool(lifejob.get("single_day_complete", False)) and not dry_run:
            mark_single_day_completion(storage, name, current_time, day_change)
        lifejob["last_run_at"] = _iso_timestamp(current_time)
        lifejob["pending_due_at"] = None
        changed = True
    return changed, events


def build_command_context(root: click.Group, command_path: str) -> tuple[click.Command, click.Context]:
    """Build one Click context chain for a dotted command path and return the final command context."""
    root_obj = getattr(root, "zush_ctx", None)
    root_context = click.Context(root, info_name=root.name or "zush")
    root_context.obj = root_obj
    current_group = root
    parent_context = root_context
    command: click.Command = root
    for part in [segment for segment in command_path.split(".") if segment]:
        if not isinstance(current_group, click.Group):
            raise click.ClickException(f"Command path '{command_path}' stops before '{part}'")
        next_command = current_group.commands.get(part)
        if next_command is None:
            raise click.ClickException(f"Unknown command path '{command_path}'")
        command = next_command
        command_context = click.Context(command, info_name=part, parent=parent_context)
        command_context.obj = root_obj
        parent_context = command_context
        if isinstance(command, click.Group):
            current_group = command
    if isinstance(command, click.Group):
        raise click.ClickException(f"Command path '{command_path}' must resolve to a command")
    return command, parent_context


def _invoke_callback(
    root: click.Group,
    command_path: str,
    context: click.Context,
    callback: Any,
    positional_args: list[str],
    keyword_args: dict[str, Any],
) -> None:
    """Invoke one resolved command callback within its Click context and root hook lifecycle."""
    hook_registry = getattr(root, "hook_registry", None)
    if hook_registry is not None:
        hook_registry.run_before_cmd(command_path)
    try:
        with context:
            callback(*positional_args, **keyword_args)
    except BaseException as exc:
        if hook_registry is not None:
            hook_registry.run_on_error(exc)
        raise
    if hook_registry is not None:
        hook_registry.run_after_cmd(command_path)


def spawn_detached_cron_job(storage: ZushStorage, job_name: str) -> None:
    """Spawn one detached Python worker that executes a stored cron job against the same base folder."""
    _spawn_detached_entry(storage, "job", job_name)


def spawn_detached_lifejob(storage: ZushStorage, lifejob_name: str) -> None:
    """Spawn one detached Python worker that executes a stored lifejob against the same base folder."""
    _spawn_detached_entry(storage, "lifejob", lifejob_name)


def _spawn_detached_entry(storage: ZushStorage, entry_type: str, entry_name: str) -> None:
    """Spawn one detached Python worker that executes a stored cron entry against the same base folder."""
    command = [
        sys.executable,
        "-c",
        (
            "import sys; "
            "from pathlib import Path; "
            "from zush import create_zush_group; "
            "from zush.core.cron import invoke_cron_job, invoke_lifejob; "
            "from zush.core.storage import DirectoryStorage; "
            "storage = DirectoryStorage(Path(sys.argv[1])); "
            "group = create_zush_group(storage=storage); "
            "invoke_cron_job(group, storage, sys.argv[3]) if sys.argv[2] == 'job' else invoke_lifejob(group, storage, sys.argv[3])"
        ),
        str(storage.config_dir()),
        entry_type,
        entry_name,
    ]
    kwargs: dict[str, Any] = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "cwd": str(storage.config_dir()),
        "env": os.environ.copy(),
    }
    if os.name == "nt":
        kwargs["creationflags"] = (
            getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        )
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(command, **kwargs)
