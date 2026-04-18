"""Cron registry helpers and scheduler entrypoints for built-in self cron commands."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click
from croniter import croniter

if TYPE_CHECKING:
    from zush.core.storage import ZushStorage


def cron_file(storage: ZushStorage) -> Path:
    """Return the base-folder cron registry path for the active storage target."""
    return storage.config_dir() / "cron.json"


def read_cron_registry(storage: ZushStorage) -> dict[str, Any]:
    """Read cron.json and return a normalized registry shape when missing or invalid."""
    file_path = cron_file(storage)
    if not file_path.exists():
        return {"jobs": {}}
    try:
        with open(file_path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (json.JSONDecodeError, OSError):
        return {"jobs": {}}
    if not isinstance(data, dict):
        return {"jobs": {}}
    jobs = data.get("jobs")
    if not isinstance(jobs, dict):
        data["jobs"] = {}
    return data


def write_cron_registry(data: dict[str, Any], storage: ZushStorage) -> None:
    """Write cron.json under the active base folder, creating the directory when needed."""
    file_path = cron_file(storage)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)


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


def add_cron_job(
    root: click.Group,
    storage: ZushStorage,
    schedule: str,
    command_path: str,
    raw_tokens: list[str],
    name: str | None = None,
    detach: bool = False,
) -> str:
    """Persist one cron job for a live dotted command path under the active base folder."""
    croniter(schedule)
    resolve_command_target(root, command_path)
    data = read_cron_registry(storage)
    args, kwargs = split_cli_tokens(raw_tokens)
    resolved_name = name or next_cron_name(data)
    jobs = data.setdefault("jobs", {})
    if not isinstance(jobs, dict):
        jobs = {}
        data["jobs"] = jobs
    if resolved_name in jobs:
        raise click.ClickException(f"Cron job '{resolved_name}' already exists")
    jobs[resolved_name] = {
        "schedule": schedule,
        "command": command_path,
        "args": args,
        "kwargs": kwargs,
        "detach": bool(detach),
        "last_run_at": None,
    }
    write_cron_registry(data, storage)
    return resolved_name


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


def remove_cron_job(storage: ZushStorage, job_name: str) -> None:
    """Remove one persisted cron job from the active base folder registry."""
    data = read_cron_registry(storage)
    jobs = data.get("jobs")
    if not isinstance(jobs, dict) or job_name not in jobs:
        raise click.ClickException(f"Unknown cron job '{job_name}'")
    del jobs[job_name]
    write_cron_registry(data, storage)


def start_cron_scheduler(root: click.Group, storage: ZushStorage) -> None:
    """Run the foreground cron scheduler loop for the active root command tree and storage target."""
    while True:
        run_due_cron_jobs(root, storage)
        time.sleep(1.0)


def run_due_cron_jobs(root: click.Group, storage: ZushStorage, now: datetime | None = None) -> None:
    """Run every cron job whose schedule matches the current minute and has not already fired for it."""
    current_time = now or datetime.now().replace(second=0, microsecond=0)
    current_slot = current_time.strftime("%Y-%m-%dT%H:%M")
    data = read_cron_registry(storage)
    jobs = data.get("jobs")
    if not isinstance(jobs, dict):
        return
    changed = False
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
        if bool(job.get("detach", False)):
            spawn_detached_cron_job(storage, name)
        else:
            invoke_cron_job(root, storage, name)
        job["last_run_at"] = current_slot
        changed = True
    if changed:
        write_cron_registry(data, storage)


def invoke_cron_job(root: click.Group, storage: ZushStorage, job_name: str) -> None:
    """Execute one persisted cron job in-process through the live Click command tree."""
    data = read_cron_registry(storage)
    jobs = data.get("jobs")
    if not isinstance(jobs, dict):
        raise click.ClickException(f"Unknown cron job '{job_name}'")
    job = jobs.get(job_name)
    if not isinstance(job, dict):
        raise click.ClickException(f"Unknown cron job '{job_name}'")
    command_path = job.get("command")
    args = job.get("args")
    kwargs = job.get("kwargs")
    if not isinstance(command_path, str) or not command_path:
        raise click.ClickException(f"Cron job '{job_name}' is missing a command path")
    command, context = build_command_context(root, command_path)
    callback = getattr(command, "callback", None)
    if not callable(callback):
        raise click.ClickException(f"Command path '{command_path}' is not executable")
    positional_args = [str(value) for value in args] if isinstance(args, list) else []
    keyword_args = {str(key): value for key, value in kwargs.items()} if isinstance(kwargs, dict) else {}
    _invoke_callback(root, command_path, context, callback, positional_args, keyword_args)


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
    command = [
        sys.executable,
        "-c",
        (
            "import sys; "
            "from pathlib import Path; "
            "from zush import create_zush_group; "
            "from zush.core.cron import invoke_cron_job; "
            "from zush.core.storage import DirectoryStorage; "
            "storage = DirectoryStorage(Path(sys.argv[1])); "
            "group = create_zush_group(storage=storage); "
            "invoke_cron_job(group, storage, sys.argv[2])"
        ),
        str(storage.config_dir()),
        job_name,
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
