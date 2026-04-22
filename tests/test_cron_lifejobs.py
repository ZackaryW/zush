"""TDD: lifetime job scheduling and execution behavior."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from zush import create_zush_group
from zush.configparse.config import Config
from zush.cron import run_due_cron_jobs, write_cron_registry
from zush.core.storage import DirectoryStorage


def test_run_due_cron_jobs_schedules_and_runs_lifejob_after_target_delay(tmp_path: Path) -> None:
    """run_due_cron_jobs should queue and later execute a lifejob after its target job runs."""
    env_root = tmp_path / "env"
    env_root.mkdir()
    target_file = tmp_path / "result.txt"
    pkg = env_root / "zush_demo"
    pkg.mkdir()
    (pkg / "__zush__.py").write_text(
        f'''
from pathlib import Path

import click

from zush.pluginloader.plugin import Plugin


plugin = Plugin()


@click.command("main")
def main_cmd() -> None:
    """Persist one main execution marker for lifejob sequencing tests."""
    target = Path(r"{target_file}")
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    target.write_text(existing + "main\\n", encoding="utf-8")


@click.command("cleanup")
def cleanup_cmd() -> None:
    """Persist one cleanup execution marker for lifejob sequencing tests."""
    target = Path(r"{target_file}")
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    target.write_text(existing + "cleanup\\n", encoding="utf-8")


plugin.group("demo").command("main", callback=main_cmd.callback)
plugin.group("demo").command("cleanup", callback=cleanup_cmd.callback)
ZushPlugin = plugin
''',
        encoding="utf-8",
    )
    storage = DirectoryStorage(tmp_path / "data")
    group = create_zush_group(config=Config(envs=[env_root], env_prefix=["zush_"]), storage=storage)
    write_cron_registry(
        {
            "registrations": {
                "main-task": {"command": "demo.main", "args": [], "kwargs": {}, "detach": False},
                "cleanup-task": {"command": "demo.cleanup", "args": [], "kwargs": {}, "detach": False},
            },
            "jobs": {
                "cron-1": {"schedule": "* * * * *", "target": "main-task", "last_run_at": None}
            },
            "lifejobs": {
                "lifejob-1": {
                    "target": "cleanup-task",
                    "target_job": "cron-1",
                    "delay_seconds": 5,
                    "pending_due_at": None,
                    "last_run_at": None,
                }
            },
        },
        storage,
    )

    run_due_cron_jobs(group, storage, now=datetime(2026, 4, 17, 10, 15, 0))
    run_due_cron_jobs(group, storage, now=datetime(2026, 4, 17, 10, 15, 4))
    run_due_cron_jobs(group, storage, now=datetime(2026, 4, 17, 10, 15, 5))

    assert target_file.read_text(encoding="utf-8") == "main\ncleanup\n"
    payload = json.loads((storage.config_dir() / "cron.json").read_text(encoding="utf-8"))
    assert payload["lifejobs"]["lifejob-1"]["pending_due_at"] is None
    assert payload["lifejobs"]["lifejob-1"]["last_run_at"] == "2026-04-17T10:15:05"


def test_run_due_cron_jobs_reschedules_pending_lifejob_to_latest_target_run(tmp_path: Path) -> None:
    """run_due_cron_jobs should overwrite an older pending lifejob when the target job runs again first."""
    env_root = tmp_path / "env"
    env_root.mkdir()
    target_file = tmp_path / "result.txt"
    pkg = env_root / "zush_demo"
    pkg.mkdir()
    (pkg / "__zush__.py").write_text(
        f'''
from pathlib import Path

import click

from zush.pluginloader.plugin import Plugin


plugin = Plugin()


@click.command("main")
def main_cmd() -> None:
    """Persist one main execution marker for lifejob reschedule tests."""
    target = Path(r"{target_file}")
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    target.write_text(existing + "main\\n", encoding="utf-8")


@click.command("cleanup")
def cleanup_cmd() -> None:
    """Persist one cleanup execution marker for lifejob reschedule tests."""
    target = Path(r"{target_file}")
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    target.write_text(existing + "cleanup\\n", encoding="utf-8")


plugin.group("demo").command("main", callback=main_cmd.callback)
plugin.group("demo").command("cleanup", callback=cleanup_cmd.callback)
ZushPlugin = plugin
''',
        encoding="utf-8",
    )
    storage = DirectoryStorage(tmp_path / "data")
    group = create_zush_group(config=Config(envs=[env_root], env_prefix=["zush_"]), storage=storage)
    write_cron_registry(
        {
            "registrations": {
                "main-task": {"command": "demo.main", "args": [], "kwargs": {}, "detach": False},
                "cleanup-task": {"command": "demo.cleanup", "args": [], "kwargs": {}, "detach": False},
            },
            "jobs": {
                "cron-1": {"schedule": "*/5 * * * *", "target": "main-task", "last_run_at": None}
            },
            "lifejobs": {
                "lifejob-1": {
                    "target": "cleanup-task",
                    "target_job": "cron-1",
                    "delay_seconds": 400,
                    "pending_due_at": None,
                    "last_run_at": None,
                }
            },
        },
        storage,
    )

    run_due_cron_jobs(group, storage, now=datetime(2026, 4, 17, 10, 15, 0))
    run_due_cron_jobs(group, storage, now=datetime(2026, 4, 17, 10, 20, 0))
    run_due_cron_jobs(group, storage, now=datetime(2026, 4, 17, 10, 21, 0))
    run_due_cron_jobs(group, storage, now=datetime(2026, 4, 17, 10, 26, 40))

    assert target_file.read_text(encoding="utf-8") == "main\nmain\ncleanup\n"
    payload = json.loads((storage.config_dir() / "cron.json").read_text(encoding="utf-8"))
    assert payload["lifejobs"]["lifejob-1"]["last_run_at"] == "2026-04-17T10:26:40"
    assert payload["lifejobs"]["lifejob-1"]["pending_due_at"] is None


def test_run_due_cron_jobs_rejects_invalid_lifejob_target_without_dispatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """run_due_cron_jobs should ignore lifejobs whose target job no longer exists."""
    storage = DirectoryStorage(tmp_path / "data")
    group = create_zush_group(config=Config(envs=[], env_prefix=["zush_"]), storage=storage)
    write_cron_registry(
        {
            "registrations": {
                "cleanup-task": {"command": "self.map", "args": [], "kwargs": {}, "detach": False}
            },
            "jobs": {},
            "lifejobs": {
                "lifejob-1": {
                    "target": "cleanup-task",
                    "target_job": "missing-job",
                    "delay_seconds": 1,
                    "pending_due_at": "2026-04-17T10:15:01",
                    "last_run_at": None,
                }
            },
        },
        storage,
    )
    seen: list[str] = []

    def fake_invoke(*_args: object, **_kwargs: object) -> None:
        """Capture unexpected lifejob dispatches for this invalid-target test."""
        seen.append("called")

    monkeypatch.setattr("zush.cron.execution.invoke_cron_job", fake_invoke)

    run_due_cron_jobs(group, storage, now=datetime(2026, 4, 17, 10, 15, 2))

    assert seen == []
