"""Daily completion ledger helpers for cron jobs that should only run once per day."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from zush.core.storage import ZushStorage


def cron_completion_file(storage: ZushStorage) -> Path:
    """Return the daily completion ledger path for the active storage target."""
    return storage.config_dir() / "cron_completion.jsonl"


def normalize_day_change(value: str | None) -> str:
    """Return one canonical HH:MM day-change boundary string or raise a click-facing error when invalid."""
    if value is None:
        return "00:00"
    try:
        parsed = datetime.strptime(value, "%H:%M")
    except ValueError as exc:
        raise click.ClickException("--day-change must use HH:MM in 24-hour time, for example 06:00") from exc
    return parsed.strftime("%H:%M")


def completion_date_key(current_time: datetime, day_change: str | None = None) -> str:
    """Return the effective completion date key after applying one configurable day-change boundary."""
    normalized = normalize_day_change(day_change)
    hour_text, minute_text = normalized.split(":", 1)
    shift = timedelta(hours=int(hour_text), minutes=int(minute_text))
    return (current_time - shift).date().isoformat()


def read_cron_completion_log(storage: ZushStorage) -> dict[str, list[str]]:
    """Read the completion ledger and return a normalized mapping of ISO dates to completed entry names."""
    file_path = cron_completion_file(storage)
    if not file_path.exists():
        return {}
    completion_map: dict[str, list[str]] = {}
    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    for line in lines:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        date_value = payload.get("date")
        completed = payload.get("completed")
        if not isinstance(date_value, str) or not isinstance(completed, list):
            continue
        names = sorted({str(name) for name in completed if isinstance(name, str) and name})
        completion_map[date_value] = names
    return completion_map


def write_cron_completion_log(completion_map: dict[str, list[str]], storage: ZushStorage) -> None:
    """Rewrite the completion ledger so each date appears once as one JSON line."""
    file_path = cron_completion_file(storage)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for date_value in sorted(completion_map.keys()):
        completed = completion_map.get(date_value, [])
        lines.append(json.dumps({"date": date_value, "completed": sorted({name for name in completed if name})}))
    file_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def has_single_day_completion(
    storage: ZushStorage,
    entry_name: str,
    current_time: datetime,
    day_change: str | None = None,
) -> bool:
    """Return whether the named cron entry is already marked complete for the effective configured day."""
    completion_map = read_cron_completion_log(storage)
    return entry_name in completion_map.get(completion_date_key(current_time, day_change), [])


def mark_single_day_completion(
    storage: ZushStorage,
    entry_name: str,
    current_time: datetime,
    day_change: str | None = None,
) -> None:
    """Mark the named cron entry complete for the effective configured day in the JSONL ledger."""
    completion_map = read_cron_completion_log(storage)
    date_key = completion_date_key(current_time, day_change)
    completed = sorted({*completion_map.get(date_key, []), entry_name})
    completion_map[date_key] = completed
    write_cron_completion_log(completion_map, storage)