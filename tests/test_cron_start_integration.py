"""TDD: integrated cron start simulations using scaled time, mock time, and dry-run mode."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from textwrap import dedent

import click
import pytest
from click.testing import CliRunner

from zush import create_zush_group
from zush.configparse.config import Config
from zush.core.cron_runtime import run_cron_scheduler
from zush.core.storage import DirectoryStorage


def _write_mock_job_plugin(env_root: Path, sink_path: Path) -> None:
    """Create one mock zush plugin package whose jobs append execution markers to a sink file."""
    pkg = env_root / "zush_demo"
    pkg.mkdir()
    (pkg / "__zush__.py").write_text(
        dedent(
            f'''
            from pathlib import Path

            import click

            from zush.pluginloader.plugin import Plugin


            plugin = Plugin()


            def _append(label: str) -> None:
                """Append one execution marker for cron integration assertions."""
                target = Path(r"{sink_path}")
                existing = target.read_text(encoding="utf-8") if target.exists() else ""
                target.write_text(existing + label + "\\n", encoding="utf-8")


            plugin.group("demo").command("main", callback=lambda: _append("main"))
            plugin.group("demo").command("every-two", callback=lambda: _append("every-two"))
            plugin.group("demo").command("cleanup", callback=lambda: _append("cleanup"))
            plugin.group("demo").command("sweep", callback=lambda: _append("sweep"))
            plugin.group("demo").command("detached", callback=lambda: _append("detached"))
            ZushPlugin = plugin
            '''
        ),
        encoding="utf-8",
    )


def test_run_cron_scheduler_dry_run_simulates_complex_interactions_without_persisting(tmp_path: Path) -> None:
    """run_cron_scheduler should simulate jobs and lifejobs over scaled mocked time without writing dry-run state."""
    env_root = tmp_path / "env"
    env_root.mkdir()
    pkg = env_root / "zush_demo"
    pkg.mkdir()
    (pkg / "__zush__.py").write_text(
        """
import click
from zush.pluginloader.plugin import Plugin


plugin = Plugin()
plugin.group("demo").command("main", callback=lambda: click.echo("main"))
plugin.group("demo").command("every-two", callback=lambda: click.echo("every-two"))
plugin.group("demo").command("cleanup", callback=lambda: click.echo("cleanup"))
plugin.group("demo").command("sweep", callback=lambda: click.echo("sweep"))
ZushPlugin = plugin
""",
        encoding="utf-8",
    )
    storage = DirectoryStorage(tmp_path / "data")
    group = create_zush_group(config=Config(envs=[env_root], env_prefix=["zush_"]), storage=storage)
    initial_payload = {
        "registrations": {
            "main-task": {"command": "demo.main", "args": [], "kwargs": {}, "detach": False},
            "two-task": {"command": "demo.every-two", "args": [], "kwargs": {}, "detach": False},
            "cleanup-task": {"command": "demo.cleanup", "args": [], "kwargs": {}, "detach": False},
            "sweep-task": {"command": "demo.sweep", "args": [], "kwargs": {}, "detach": False},
        },
        "jobs": {
            "cron-1": {"schedule": "*/5 * * * *", "target": "main-task", "last_run_at": None},
            "cron-2": {"schedule": "*/2 * * * *", "target": "two-task", "last_run_at": None},
        },
        "lifejobs": {
            "lifejob-1": {
                "target": "cleanup-task",
                "target_job": "cron-1",
                "delay_seconds": 90,
                "pending_due_at": None,
                "last_run_at": None,
            },
            "lifejob-2": {
                "target": "sweep-task",
                "target_job": "cron-2",
                "delay_seconds": 30,
                "pending_due_at": None,
                "last_run_at": None,
            },
        },
    }
    cron_path = storage.config_dir() / "cron.json"
    cron_path.parent.mkdir(parents=True, exist_ok=True)
    cron_path.write_text(json.dumps(initial_payload, indent=2), encoding="utf-8")
    seen: list[str] = []

    run_cron_scheduler(
        group,
        storage,
        scale=30.0,
        mocktime=datetime(2026, 4, 17, 10, 15, 0),
        dry_run=True,
        emit=seen.append,
        max_ticks=8,
        sleeper=lambda _seconds: None,
    )

    assert seen == [
        "dry-run job cron-1 at 2026-04-17T10:15:00 -> demo.main",
        "dry-run job cron-2 at 2026-04-17T10:16:00 -> demo.every-two",
        "dry-run lifejob lifejob-1 at 2026-04-17T10:16:30 -> demo.cleanup",
        "dry-run lifejob lifejob-2 at 2026-04-17T10:16:30 -> demo.sweep",
        "dry-run job cron-2 at 2026-04-17T10:18:00 -> demo.every-two",
        "dry-run lifejob lifejob-2 at 2026-04-17T10:18:30 -> demo.sweep",
    ]
    assert json.loads(cron_path.read_text(encoding="utf-8")) == initial_payload


def test_run_cron_scheduler_executes_mock_jobs_and_persists_runtime_state(tmp_path: Path) -> None:
    """run_cron_scheduler should execute mock jobs and persist job plus lifejob timestamps when not in dry-run mode."""
    env_root = tmp_path / "env"
    env_root.mkdir()
    sink_path = tmp_path / "executions.txt"
    _write_mock_job_plugin(env_root, sink_path)
    storage = DirectoryStorage(tmp_path / "data")
    group = create_zush_group(config=Config(envs=[env_root], env_prefix=["zush_"]), storage=storage)
    cron_path = storage.config_dir() / "cron.json"
    cron_path.parent.mkdir(parents=True, exist_ok=True)
    cron_path.write_text(
        json.dumps(
            {
                "registrations": {
                    "main-task": {"command": "demo.main", "args": [], "kwargs": {}, "detach": False},
                    "cleanup-task": {"command": "demo.cleanup", "args": [], "kwargs": {}, "detach": False},
                    "two-task": {"command": "demo.every-two", "args": [], "kwargs": {}, "detach": False},
                },
                "jobs": {
                    "cron-1": {"schedule": "*/5 * * * *", "target": "main-task", "last_run_at": None},
                    "cron-2": {"schedule": "*/2 * * * *", "target": "two-task", "last_run_at": None},
                },
                "lifejobs": {
                    "lifejob-1": {
                        "target": "cleanup-task",
                        "target_job": "cron-1",
                        "delay_seconds": 90,
                        "pending_due_at": None,
                        "last_run_at": None,
                    }
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    run_cron_scheduler(
        group,
        storage,
        scale=30.0,
        mocktime=datetime(2026, 4, 17, 10, 15, 0),
        dry_run=False,
        max_ticks=8,
        sleeper=lambda _seconds: None,
    )

    assert sink_path.read_text(encoding="utf-8") == "main\nevery-two\ncleanup\nevery-two\n"
    payload = json.loads(cron_path.read_text(encoding="utf-8"))
    assert payload["jobs"]["cron-1"]["last_run_at"] == "2026-04-17T10:15"
    assert payload["jobs"]["cron-2"]["last_run_at"] == "2026-04-17T10:18"
    assert payload["lifejobs"]["lifejob-1"]["last_run_at"] == "2026-04-17T10:16:30"
    assert payload["lifejobs"]["lifejob-1"]["pending_due_at"] is None


def test_run_cron_scheduler_dry_run_reports_detached_mock_jobs_without_executing_them(tmp_path: Path) -> None:
    """run_cron_scheduler should emit dry-run lines for detached mock jobs and leave their sink untouched."""
    env_root = tmp_path / "env"
    env_root.mkdir()
    sink_path = tmp_path / "executions.txt"
    _write_mock_job_plugin(env_root, sink_path)
    storage = DirectoryStorage(tmp_path / "data")
    group = create_zush_group(config=Config(envs=[env_root], env_prefix=["zush_"]), storage=storage)
    cron_path = storage.config_dir() / "cron.json"
    cron_path.parent.mkdir(parents=True, exist_ok=True)
    initial_payload = {
        "registrations": {
            "detached-task": {"command": "demo.detached", "args": [], "kwargs": {}, "detach": True},
            "cleanup-task": {"command": "demo.cleanup", "args": [], "kwargs": {}, "detach": True},
        },
        "jobs": {
            "cron-1": {"schedule": "* * * * *", "target": "detached-task", "last_run_at": None}
        },
        "lifejobs": {
            "lifejob-1": {
                "target": "cleanup-task",
                "target_job": "cron-1",
                "delay_seconds": 30,
                "pending_due_at": None,
                "last_run_at": None,
            }
        },
    }
    cron_path.write_text(json.dumps(initial_payload, indent=2), encoding="utf-8")
    seen: list[str] = []

    run_cron_scheduler(
        group,
        storage,
        scale=30.0,
        mocktime=datetime(2026, 4, 17, 10, 15, 0),
        dry_run=True,
        emit=seen.append,
        max_ticks=2,
        sleeper=lambda _seconds: None,
    )

    assert seen == [
        "dry-run job cron-1 at 2026-04-17T10:15:00 -> demo.detached",
        "dry-run lifejob lifejob-1 at 2026-04-17T10:15:30 -> demo.cleanup",
    ]
    assert not sink_path.exists()
    assert json.loads(cron_path.read_text(encoding="utf-8")) == initial_payload


def test_self_cron_start_passes_runtime_options_to_scheduler(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """self cron start should pass scale, mocktime, and dry-run options into the scheduler helper."""
    storage = DirectoryStorage(tmp_path / "data")
    storage.config_dir().mkdir(parents=True, exist_ok=True)
    storage.config_file().write_text(
        'envs = []\nenv_prefix = ["zush_"]\ninclude_current_env = false\n',
        encoding="utf-8",
    )
    group = create_zush_group(storage=storage)
    seen: list[tuple[object, object, float, object, bool]] = []

    def fake_run_scheduler(
        root: click.Group,
        active_storage: DirectoryStorage,
        *,
        scale: float,
        mocktime: object,
        dry_run: bool,
    ) -> None:
        """Capture one cron scheduler start request for assertion in this test."""
        seen.append((root, active_storage, scale, mocktime, dry_run))

    monkeypatch.setattr("zush.core.group.run_cron_scheduler", fake_run_scheduler)

    result = CliRunner().invoke(
        group,
        ["self", "cron", "start", "--scale", "60", "--mocktime", "2026-04-17T10:15:00", "--dry-run"],
    )

    assert result.exit_code == 0, (result.output, repr(result.exception))
    assert seen == [(group, storage, 60.0, "2026-04-17T10:15:00", True)]
