"""TDD: self cron single-day-complete CLI behavior."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from zush.core.bootstrap import create_zush_group
from zush.core.storage import DirectoryStorage


def test_self_cron_add_persists_single_day_complete_job_flag(tmp_path: Path) -> None:
    """self cron add should persist the single-day-complete flag on normal jobs."""
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
                    "main-task": {"command": "self.map", "args": [], "kwargs": {}, "detach": False}
                },
                "jobs": {},
                "lifejobs": {},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    group = create_zush_group(storage=storage)

    result = CliRunner().invoke(group, ["self", "cron", "add", "main-task", "*/5 * * * *", "-sdc"])

    assert result.exit_code == 0, (result.output, repr(result.exception))
    payload = json.loads((storage.config_dir() / "cron.json").read_text(encoding="utf-8"))
    assert payload["jobs"]["cron-1"]["single_day_complete"] is True


def test_self_cron_add_persists_single_day_complete_lifejob_flag(tmp_path: Path) -> None:
    """self cron add should persist the single-day-complete flag on lifejobs."""
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
        ["self", "cron", "add", "cleanup-task", "--lifejob", "cron-1", "--delay", "30", "-sdc"],
    )

    assert result.exit_code == 0, (result.output, repr(result.exception))
    payload = json.loads((storage.config_dir() / "cron.json").read_text(encoding="utf-8"))
    assert payload["lifejobs"]["lifejob-1"]["single_day_complete"] is True


def test_self_cron_add_persists_custom_day_change_for_single_day_complete_entries(tmp_path: Path) -> None:
    """self cron add should persist a custom day-change boundary on jobs and lifejobs."""
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

    job_result = CliRunner().invoke(
        group,
        ["self", "cron", "add", "main-task", "0 6 * * *", "-sdc", "--day-change", "06:00"],
    )
    lifejob_result = CliRunner().invoke(
        group,
        [
            "self",
            "cron",
            "add",
            "cleanup-task",
            "--lifejob",
            "cron-1",
            "--delay",
            "30",
            "-sdc",
            "--day-change",
            "06:00",
        ],
    )

    assert job_result.exit_code == 0, (job_result.output, repr(job_result.exception))
    assert lifejob_result.exit_code == 0, (lifejob_result.output, repr(lifejob_result.exception))
    payload = json.loads((storage.config_dir() / "cron.json").read_text(encoding="utf-8"))
    assert payload["jobs"]["cron-2"]["day_change"] == "06:00"
    assert payload["lifejobs"]["lifejob-1"]["day_change"] == "06:00"
