"""TDD: self cron lifejob CLI behavior."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from zush.core.bootstrap import create_zush_group
from zush.core.storage import DirectoryStorage


def test_self_cron_add_lifejob_persists_delayed_follower(tmp_path: Path) -> None:
    """self cron add should persist a lifejob when called with --lifejob and --delay."""
    storage = DirectoryStorage(tmp_path / "data")
    storage.config_dir().mkdir(parents=True, exist_ok=True)
    storage.config_file().write_text(
        'envs = []\nenv_prefix = ["zush_"]\ninclude_current_env = false\n',
        encoding="utf-8",
    )
    (storage.config_dir() / "cron.json").write_text(
        json.dumps(
            {
                "registrations": {
                    "main-task": {"command": "self.map", "args": [], "kwargs": {}, "detach": False},
                    "cleanup-task": {"command": "self.diagnostics", "args": [], "kwargs": {}, "detach": False},
                },
                "jobs": {
                    "cron-1": {"schedule": "*/5 * * * *", "target": "main-task", "last_run_at": None}
                },
                "lifejobs": {},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    group = create_zush_group(storage=storage)

    result = CliRunner().invoke(
        group,
        ["self", "cron", "add", "cleanup-task", "--lifejob", "cron-1", "--delay", "30"],
    )

    assert result.exit_code == 0, (result.output, repr(result.exception))
    assert "lifejob-1" in result.output
    payload = json.loads((storage.config_dir() / "cron.json").read_text(encoding="utf-8"))
    assert payload["lifejobs"]["lifejob-1"]["target"] == "cleanup-task"
    assert payload["lifejobs"]["lifejob-1"]["target_job"] == "cron-1"
    assert payload["lifejobs"]["lifejob-1"]["delay_seconds"] == 30
    assert payload["lifejobs"]["lifejob-1"]["pending_due_at"] is None
    assert payload["lifejobs"]["lifejob-1"]["last_run_at"] is None
    assert isinstance(payload["lifejobs"]["lifejob-1"]["created_at"], str)


def test_self_cron_list_prints_lifejobs_section(tmp_path: Path) -> None:
    """self cron list should print persisted lifejobs alongside registrations and jobs."""
    storage = DirectoryStorage(tmp_path / "data")
    storage.config_dir().mkdir(parents=True, exist_ok=True)
    storage.config_file().write_text(
        'envs = []\nenv_prefix = ["zush_"]\ninclude_current_env = false\n',
        encoding="utf-8",
    )
    (storage.config_dir() / "cron.json").write_text(
        json.dumps(
            {
                "registrations": {
                    "main-task": {"command": "self.map", "args": [], "kwargs": {}, "detach": False},
                    "cleanup-task": {"command": "self.diagnostics", "args": [], "kwargs": {}, "detach": True},
                },
                "jobs": {
                    "cron-1": {"schedule": "*/5 * * * *", "target": "main-task", "last_run_at": None}
                },
                "lifejobs": {
                    "lifejob-1": {
                        "target": "cleanup-task",
                        "target_job": "cron-1",
                        "delay_seconds": 30,
                        "pending_due_at": "2026-04-17T10:15:30",
                        "last_run_at": "2026-04-17T10:10:30",
                    }
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    group = create_zush_group(storage=storage)

    result = CliRunner().invoke(group, ["self", "cron", "list"])

    assert result.exit_code == 0, (result.output, repr(result.exception))
    assert "[lifejobs]" in result.output
    assert "lifejob-1 | cleanup-task | cron-1 | 30 | 2026-04-17T10:15:30 | 2026-04-17T10:10:30" in result.output


def test_self_cron_remove_cascades_attached_lifejobs(tmp_path: Path) -> None:
    """self cron remove should delete any lifejobs attached to the removed target job."""
    storage = DirectoryStorage(tmp_path / "data")
    storage.config_dir().mkdir(parents=True, exist_ok=True)
    storage.config_file().write_text(
        'envs = []\nenv_prefix = ["zush_"]\ninclude_current_env = false\n',
        encoding="utf-8",
    )
    (storage.config_dir() / "cron.json").write_text(
        json.dumps(
            {
                "registrations": {
                    "main-task": {"command": "self.map", "args": [], "kwargs": {}, "detach": False},
                    "cleanup-task": {"command": "self.diagnostics", "args": [], "kwargs": {}, "detach": False},
                },
                "jobs": {
                    "cron-1": {"schedule": "*/5 * * * *", "target": "main-task", "last_run_at": None}
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
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    group = create_zush_group(storage=storage)

    result = CliRunner().invoke(group, ["self", "cron", "remove", "cron-1"])

    assert result.exit_code == 0, (result.output, repr(result.exception))
    payload = json.loads((storage.config_dir() / "cron.json").read_text(encoding="utf-8"))
    assert payload["jobs"] == {}
    assert payload["lifejobs"] == {}


def test_self_cron_add_allows_schedule_and_lifejob_in_one_call(tmp_path: Path) -> None:
    """self cron add should persist both a schedule job and a delayed lifejob when both inputs are provided."""
    storage = DirectoryStorage(tmp_path / "data")
    storage.config_dir().mkdir(parents=True, exist_ok=True)
    storage.config_file().write_text(
        'envs = []\nenv_prefix = ["zush_"]\ninclude_current_env = false\n',
        encoding="utf-8",
    )
    (storage.config_dir() / "cron.json").write_text(
        json.dumps(
            {
                "registrations": {
                    "main-task": {"command": "self.map", "args": [], "kwargs": {}, "detach": False},
                    "cleanup-task": {"command": "self.diagnostics", "args": [], "kwargs": {}, "detach": False},
                },
                "jobs": {
                    "cron-1": {"schedule": "*/5 * * * *", "target": "main-task", "last_run_at": None}
                },
                "lifejobs": {},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    group = create_zush_group(storage=storage)

    result = CliRunner().invoke(
        group,
        ["self", "cron", "add", "cleanup-task", "*/10 * * * *", "--lifejob", "cron-1", "--delay", "30"],
    )

    assert result.exit_code == 0, (result.output, repr(result.exception))
    payload = json.loads((storage.config_dir() / "cron.json").read_text(encoding="utf-8"))
    assert payload["jobs"]["cron-2"]["schedule"] == "*/10 * * * *"
    assert payload["jobs"]["cron-2"]["target"] == "cleanup-task"
    assert payload["jobs"]["cron-2"]["last_run_at"] is None
    assert isinstance(payload["jobs"]["cron-2"]["created_at"], str)
    assert payload["lifejobs"]["lifejob-1"]["target"] == "cleanup-task"
    assert payload["lifejobs"]["lifejob-1"]["target_job"] == "cron-1"
    assert payload["lifejobs"]["lifejob-1"]["delay_seconds"] == 30
    assert payload["lifejobs"]["lifejob-1"]["pending_due_at"] is None
    assert payload["lifejobs"]["lifejob-1"]["last_run_at"] is None
    assert isinstance(payload["lifejobs"]["lifejob-1"]["created_at"], str)
