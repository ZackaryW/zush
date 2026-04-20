"""Scheduler runtime helpers for simulated cron time, dry-run output, and start-loop controls."""

from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Callable

import click

from zush.core.cron import process_due_cron_registry, read_cron_registry, run_due_cron_jobs

if TYPE_CHECKING:
    from zush.core.storage import ZushStorage


@dataclass(slots=True)
class CronSchedulerClock:
    """Mutable simulated clock used by cron start to advance time at a configured scale."""

    start_time: datetime
    scale: float = 1.0
    _current_time: datetime = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Validate scale input and initialize the mutable current time from the configured start time."""
        if self.scale <= 0:
            raise click.ClickException("--scale must be greater than 0")
        self._current_time = self.start_time

    def now(self) -> datetime:
        """Return the current simulated scheduler timestamp."""
        return self._current_time

    def advance(self, real_seconds: float) -> datetime:
        """Advance simulated time by the configured scale factor and return the new timestamp."""
        self._current_time = self._current_time + timedelta(seconds=real_seconds * self.scale)
        return self._current_time


def parse_cron_mocktime(value: str | None) -> datetime | None:
    """Parse one optional ISO timestamp for scheduler simulation and raise a click-facing error when invalid."""
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise click.ClickException("--mocktime must be an ISO datetime like 2026-04-17T10:15:00") from exc


def run_cron_scheduler(
    root: click.Group,
    storage: ZushStorage,
    *,
    scale: float = 1.0,
    mocktime: str | datetime | None = None,
    dry_run: bool = False,
    emit: Callable[[str], None] | None = None,
    max_ticks: int | None = None,
    sleep_seconds: float = 1.0,
    sleeper: Callable[[float], None] | None = None,
) -> None:
    """Run the cron scheduler loop with optional simulated time, dry-run output, and bounded test ticks."""
    start_time = parse_cron_mocktime(mocktime) if isinstance(mocktime, str) else mocktime
    clock = CronSchedulerClock(start_time=start_time or datetime.now(), scale=scale)
    emit_line = emit or (lambda _line: None)
    sleep_fn = sleeper or time.sleep
    active_registry = copy.deepcopy(read_cron_registry(storage)) if dry_run else None
    tick_count = 0
    while True:
        current_time = clock.now()
        if dry_run:
            assert active_registry is not None
            _, events = process_due_cron_registry(root, storage, active_registry, current_time, dry_run=True)
        else:
            events = run_due_cron_jobs(root, storage, now=current_time)
        for event in events:
            emit_line(event)
        tick_count += 1
        if max_ticks is not None and tick_count >= max_ticks:
            return
        sleep_fn(sleep_seconds)
        clock.advance(sleep_seconds)