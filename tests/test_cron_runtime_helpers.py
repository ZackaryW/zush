"""TDD: cron runtime helper behavior for scaled and mocked time."""

from __future__ import annotations

from datetime import datetime

import click
import pytest

from zush.cron.runtime import CronSchedulerClock, parse_cron_mocktime


def test_parse_cron_mocktime_accepts_iso_datetime() -> None:
    """parse_cron_mocktime should accept second-resolution ISO timestamps for scheduler simulation."""
    parsed = parse_cron_mocktime("2026-04-17T10:15:30")

    assert parsed == datetime(2026, 4, 17, 10, 15, 30)


def test_parse_cron_mocktime_rejects_invalid_values() -> None:
    """parse_cron_mocktime should reject invalid timestamps with a click-facing error."""
    with pytest.raises(click.ClickException):
        parse_cron_mocktime("not-a-time")


def test_cron_scheduler_clock_advances_by_scaled_seconds() -> None:
    """CronSchedulerClock should advance simulated time by the configured scale factor."""
    clock = CronSchedulerClock(start_time=datetime(2026, 4, 17, 10, 15, 0), scale=30.0)

    assert clock.now() == datetime(2026, 4, 17, 10, 15, 0)

    clock.advance(1.0)
    assert clock.now() == datetime(2026, 4, 17, 10, 15, 30)

    clock.advance(2.0)
    assert clock.now() == datetime(2026, 4, 17, 10, 16, 30)
