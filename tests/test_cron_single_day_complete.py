"""TDD: single-day completion behavior for cron jobs and lifejobs."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from zush import create_zush_group
from zush.configparse.config import Config
from zush.core.cron import run_due_cron_jobs, write_cron_registry
from zush.core.storage import DirectoryStorage


def _write_completion_demo(env_root: Path, sink_path: Path) -> None:
    """Create one demo plugin whose commands append execution markers to a sink file."""
    pkg = env_root / "zush_demo"
    pkg.mkdir()
    (pkg / "__zush__.py").write_text(
        f'''
from pathlib import Path

import click

from zush.pluginloader.plugin import Plugin


plugin = Plugin()


def _append(label: str) -> None:
    """Append one execution marker for completion-ledger assertions."""
    target = Path(r"{sink_path}")
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    target.write_text(existing + label + "\\n", encoding="utf-8")


plugin.group("demo").command("main", callback=lambda: _append("main"))
plugin.group("demo").command("cleanup", callback=lambda: _append("cleanup"))
ZushPlugin = plugin
''',
        encoding="utf-8",
    )


def test_run_due_cron_jobs_skips_single_day_complete_job_after_same_day_completion(tmp_path: Path) -> None:
    """run_due_cron_jobs should execute a single-day-complete job once per day and skip later same-day matches."""
    env_root = tmp_path / "env"
    env_root.mkdir()
    sink_path = tmp_path / "result.txt"
    _write_completion_demo(env_root, sink_path)
    storage = DirectoryStorage(tmp_path / "data")
    group = create_zush_group(config=Config(envs=[env_root], env_prefix=["zush_"]), storage=storage)
    write_cron_registry(
        {
            "registrations": {
                "main-task": {"command": "demo.main", "args": [], "kwargs": {}, "detach": False},
            },
            "jobs": {
                "cron-1": {
                    "schedule": "* * * * *",
                    "target": "main-task",
                    "single_day_complete": True,
                    "last_run_at": None,
                }
            },
            "lifejobs": {},
        },
        storage,
    )

    run_due_cron_jobs(group, storage, now=datetime(2026, 4, 17, 10, 15, 0))
    run_due_cron_jobs(group, storage, now=datetime(2026, 4, 17, 10, 16, 0))
    run_due_cron_jobs(group, storage, now=datetime(2026, 4, 18, 10, 15, 0))

    assert sink_path.read_text(encoding="utf-8") == "main\nmain\n"
    payload = json.loads((storage.config_dir() / "cron.json").read_text(encoding="utf-8"))
    assert payload["jobs"]["cron-1"]["last_run_at"] == "2026-04-18T10:15"
    completion_lines = [
        json.loads(line)
        for line in (storage.config_dir() / "cron_completion.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert completion_lines == [
        {"date": "2026-04-17", "completed": ["cron-1"]},
        {"date": "2026-04-18", "completed": ["cron-1"]},
    ]


def test_run_due_cron_jobs_skips_single_day_complete_lifejob_after_same_day_completion(tmp_path: Path) -> None:
    """run_due_cron_jobs should execute a single-day-complete lifejob once per day and skip later same-day due times."""
    env_root = tmp_path / "env"
    env_root.mkdir()
    sink_path = tmp_path / "result.txt"
    _write_completion_demo(env_root, sink_path)
    storage = DirectoryStorage(tmp_path / "data")
    group = create_zush_group(config=Config(envs=[env_root], env_prefix=["zush_"]), storage=storage)
    write_cron_registry(
        {
            "registrations": {
                "main-task": {"command": "demo.main", "args": [], "kwargs": {}, "detach": False},
                "cleanup-task": {"command": "demo.cleanup", "args": [], "kwargs": {}, "detach": False},
            },
            "jobs": {
                "cron-1": {"schedule": "0 10 * * *", "target": "main-task", "last_run_at": None}
            },
            "lifejobs": {
                "lifejob-1": {
                    "target": "cleanup-task",
                    "target_job": "cron-1",
                    "delay_seconds": 30,
                    "single_day_complete": True,
                    "pending_due_at": None,
                    "last_run_at": None,
                }
            },
        },
        storage,
    )

    run_due_cron_jobs(group, storage, now=datetime(2026, 4, 17, 10, 0, 0))
    run_due_cron_jobs(group, storage, now=datetime(2026, 4, 17, 10, 0, 30))
    run_due_cron_jobs(group, storage, now=datetime(2026, 4, 17, 10, 0, 31))
    run_due_cron_jobs(group, storage, now=datetime(2026, 4, 18, 10, 0, 0))
    run_due_cron_jobs(group, storage, now=datetime(2026, 4, 18, 10, 0, 30))

    assert sink_path.read_text(encoding="utf-8") == "main\ncleanup\nmain\ncleanup\n"
    completion_lines = [
        json.loads(line)
        for line in (storage.config_dir() / "cron_completion.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert completion_lines == [
        {"date": "2026-04-17", "completed": ["lifejob-1"]},
        {"date": "2026-04-18", "completed": ["lifejob-1"]},
    ]


def test_run_due_cron_jobs_uses_custom_day_change_for_single_day_complete_jobs(tmp_path: Path) -> None:
    """run_due_cron_jobs should treat times before a custom day-change boundary as part of the previous completion day."""
    env_root = tmp_path / "env"
    env_root.mkdir()
    sink_path = tmp_path / "result.txt"
    _write_completion_demo(env_root, sink_path)
    storage = DirectoryStorage(tmp_path / "data")
    group = create_zush_group(config=Config(envs=[env_root], env_prefix=["zush_"]), storage=storage)
    write_cron_registry(
        {
            "registrations": {
                "main-task": {"command": "demo.main", "args": [], "kwargs": {}, "detach": False},
            },
            "jobs": {
                "cron-1": {
                    "schedule": "* * * * *",
                    "target": "main-task",
                    "single_day_complete": True,
                    "day_change": "06:00",
                    "last_run_at": None,
                }
            },
            "lifejobs": {},
        },
        storage,
    )

    run_due_cron_jobs(group, storage, now=datetime(2026, 4, 17, 5, 30, 0))
    run_due_cron_jobs(group, storage, now=datetime(2026, 4, 17, 5, 45, 0))
    run_due_cron_jobs(group, storage, now=datetime(2026, 4, 17, 6, 0, 0))

    assert sink_path.read_text(encoding="utf-8") == "main\nmain\n"
    completion_lines = [
        json.loads(line)
        for line in (storage.config_dir() / "cron_completion.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert completion_lines == [
        {"date": "2026-04-16", "completed": ["cron-1"]},
        {"date": "2026-04-17", "completed": ["cron-1"]},
    ]


def test_run_due_cron_jobs_uses_custom_day_change_for_single_day_complete_lifejobs(tmp_path: Path) -> None:
    """run_due_cron_jobs should apply a custom day-change boundary when deciding whether a lifejob already completed."""
    env_root = tmp_path / "env"
    env_root.mkdir()
    sink_path = tmp_path / "result.txt"
    _write_completion_demo(env_root, sink_path)
    storage = DirectoryStorage(tmp_path / "data")
    group = create_zush_group(config=Config(envs=[env_root], env_prefix=["zush_"]), storage=storage)
    write_cron_registry(
        {
            "registrations": {
                "main-task": {"command": "demo.main", "args": [], "kwargs": {}, "detach": False},
                "cleanup-task": {"command": "demo.cleanup", "args": [], "kwargs": {}, "detach": False},
            },
            "jobs": {
                "cron-1": {"schedule": "0 5,6 * * *", "target": "main-task", "last_run_at": None}
            },
            "lifejobs": {
                "lifejob-1": {
                    "target": "cleanup-task",
                    "target_job": "cron-1",
                    "delay_seconds": 30,
                    "single_day_complete": True,
                    "day_change": "06:00",
                    "pending_due_at": None,
                    "last_run_at": None,
                }
            },
        },
        storage,
    )

    run_due_cron_jobs(group, storage, now=datetime(2026, 4, 17, 5, 0, 0))
    run_due_cron_jobs(group, storage, now=datetime(2026, 4, 17, 5, 0, 30))
    run_due_cron_jobs(group, storage, now=datetime(2026, 4, 17, 5, 1, 0))
    run_due_cron_jobs(group, storage, now=datetime(2026, 4, 17, 6, 0, 0))
    run_due_cron_jobs(group, storage, now=datetime(2026, 4, 17, 6, 0, 30))

    assert sink_path.read_text(encoding="utf-8") == "main\ncleanup\nmain\ncleanup\n"
    completion_lines = [
        json.loads(line)
        for line in (storage.config_dir() / "cron_completion.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert completion_lines == [
        {"date": "2026-04-16", "completed": ["lifejob-1"]},
        {"date": "2026-04-17", "completed": ["lifejob-1"]},
    ]
