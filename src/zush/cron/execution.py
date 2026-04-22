"""Cron scheduler execution helpers and detached dispatch for jobs and lifejobs."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

import click
from croniter import croniter

from zush.cron.completion import has_single_day_completion, mark_single_day_completion
from zush.cron.registry import (
    _resolve_registered_target,
    read_cron_registry,
    resolve_cron_registration,
    write_cron_registry,
)

if TYPE_CHECKING:
    from zush.core.storage import ZushStorage


def _iso_timestamp(value: datetime) -> str:
    """Return one stable second-resolution ISO timestamp for cron state persistence."""
    return value.replace(microsecond=0).isoformat(timespec="seconds")


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
            "from zush.cron.execution import invoke_cron_job, invoke_lifejob; "
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
