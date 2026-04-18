"""TDD: cron registry execution and detached dispatch."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import click
import pytest

from zush import create_zush_group
from zush.configparse.config import Config
from zush.core.context import HookRegistry, ZushCtx
from zush.core.cron import (
    invoke_cron_job,
    run_due_cron_jobs,
    split_cli_tokens,
    spawn_detached_cron_job,
    write_cron_registry,
)
from zush.core.group import ZushGroup
from zush.core.storage import DirectoryStorage


def test_run_due_cron_jobs_invokes_matching_command_and_updates_last_run(tmp_path: Path) -> None:
    """run_due_cron_jobs should invoke each matching live command once for the current minute slot."""
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


@click.command("run")
@click.argument("name")
@click.option("--count")
def run_cmd(name: str, count: str | None) -> None:
    """Persist one execution marker so the cron test can assert the live command ran."""
    target = Path(r"{target_file}")
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    target.write_text(existing + f"{{name}}:{{count}}\\n", encoding="utf-8")


plugin.group("demo").command("run", callback=run_cmd.callback)
ZushPlugin = plugin
''',
        encoding="utf-8",
    )
    storage = DirectoryStorage(tmp_path / "data")
    group = create_zush_group(config=Config(envs=[env_root], env_prefix=["zush_"]), storage=storage)
    write_cron_registry(
        {
            "jobs": {
                "cron-1": {
                    "schedule": "* * * * *",
                    "command": "demo.run",
                    "args": ["alpha"],
                    "kwargs": {"count": "2"},
                    "detach": False,
                    "last_run_at": None,
                }
            }
        },
        storage,
    )
    current_time = datetime(2026, 4, 17, 10, 15)

    run_due_cron_jobs(group, storage, now=current_time)
    run_due_cron_jobs(group, storage, now=current_time)

    assert target_file.read_text(encoding="utf-8") == "alpha:2\n"
    payload = json.loads((storage.config_dir() / "cron.json").read_text(encoding="utf-8"))
    assert payload["jobs"]["cron-1"]["last_run_at"] == "2026-04-17T10:15"


def test_run_due_cron_jobs_dispatches_detached_jobs_without_in_process_invoke(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """run_due_cron_jobs should hand detached jobs to the detached dispatcher instead of invoking them inline."""
    storage = DirectoryStorage(tmp_path / "data")
    group = create_zush_group(config=Config(envs=[], env_prefix=["zush_"]), storage=storage)
    write_cron_registry(
        {
            "jobs": {
                "nightly": {
                    "schedule": "* * * * *",
                    "command": "self.map",
                    "args": [],
                    "kwargs": {},
                    "detach": True,
                    "last_run_at": None,
                }
            }
        },
        storage,
    )
    seen: list[str] = []

    def fake_spawn(active_storage: DirectoryStorage, job_name: str) -> None:
        """Capture one detached dispatch so the test can assert the scheduler path."""
        seen.append(f"{active_storage.config_dir()}::{job_name}")

    monkeypatch.setattr("zush.core.cron.spawn_detached_cron_job", fake_spawn)

    run_due_cron_jobs(group, storage, now=datetime(2026, 4, 17, 10, 15))

    assert seen == [f"{storage.config_dir()}::nightly"]
    payload = json.loads((storage.config_dir() / "cron.json").read_text(encoding="utf-8"))
    assert payload["jobs"]["nightly"]["last_run_at"] == "2026-04-17T10:15"


@pytest.mark.parametrize(
    ("schedule", "now", "should_run"),
    [
        ("* * * * *", datetime(2026, 4, 17, 10, 15), True),
        ("*/15 * * * *", datetime(2026, 4, 17, 10, 15), True),
        ("*/15 * * * *", datetime(2026, 4, 17, 10, 14), False),
        ("0,30 * * * *", datetime(2026, 4, 17, 10, 30), True),
        ("0,30 * * * *", datetime(2026, 4, 17, 10, 15), False),
        ("10-20 * * * *", datetime(2026, 4, 17, 10, 15), True),
        ("10-20 * * * *", datetime(2026, 4, 17, 10, 21), False),
        ("0 9 * * 1-5", datetime(2026, 4, 20, 9, 0), True),
        ("0 9 * * 1-5", datetime(2026, 4, 19, 9, 0), False),
        ("0 0 1 * *", datetime(2026, 5, 1, 0, 0), True),
        ("0 0 1 * *", datetime(2026, 5, 2, 0, 0), False),
        ("0 0 1 jan *", datetime(2026, 1, 1, 0, 0), True),
        ("0 0 1 jan *", datetime(2026, 2, 1, 0, 0), False),
        ("0 0 * * mon", datetime(2026, 4, 20, 0, 0), True),
        ("0 0 * * mon", datetime(2026, 4, 21, 0, 0), False),
    ],
)
def test_run_due_cron_jobs_covers_crontab_schedule_matrix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    schedule: str,
    now: datetime,
    should_run: bool,
) -> None:
    """run_due_cron_jobs should respect representative wildcard, step, list, range, and calendar cron shapes."""
    storage = DirectoryStorage(tmp_path / "data")
    group = create_zush_group(config=Config(envs=[], env_prefix=["zush_"]), storage=storage)
    write_cron_registry(
        {
            "jobs": {
                "matrix": {
                    "schedule": schedule,
                    "command": "self.map",
                    "args": [],
                    "kwargs": {},
                    "detach": False,
                    "last_run_at": None,
                }
            }
        },
        storage,
    )
    seen: list[str] = []

    def fake_invoke(_root: click.Group, _storage: DirectoryStorage, job_name: str) -> None:
        """Capture due invocations so the schedule matrix can assert match behavior without running commands."""
        seen.append(job_name)

    monkeypatch.setattr("zush.core.cron.invoke_cron_job", fake_invoke)

    run_due_cron_jobs(group, storage, now=now)

    payload = json.loads((storage.config_dir() / "cron.json").read_text(encoding="utf-8"))
    if should_run:
        assert seen == ["matrix"]
        assert payload["jobs"]["matrix"]["last_run_at"] == now.strftime("%Y-%m-%dT%H:%M")
    else:
        assert seen == []
        assert payload["jobs"]["matrix"]["last_run_at"] is None


def test_run_due_cron_jobs_ignores_invalid_schedule_without_dispatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """run_due_cron_jobs should ignore invalid cron expressions rather than dispatching a broken job."""
    storage = DirectoryStorage(tmp_path / "data")
    group = create_zush_group(config=Config(envs=[], env_prefix=["zush_"]), storage=storage)
    write_cron_registry(
        {
            "jobs": {
                "broken": {
                    "schedule": "not a crontab",
                    "command": "self.map",
                    "args": [],
                    "kwargs": {},
                    "detach": False,
                    "last_run_at": None,
                }
            }
        },
        storage,
    )
    seen: list[str] = []

    def fake_invoke(_root: click.Group, _storage: DirectoryStorage, job_name: str) -> None:
        """Capture invocations to prove invalid schedules are skipped."""
        seen.append(job_name)

    monkeypatch.setattr("zush.core.cron.invoke_cron_job", fake_invoke)

    run_due_cron_jobs(group, storage, now=datetime(2026, 4, 17, 10, 15))

    assert seen == []
    payload = json.loads((storage.config_dir() / "cron.json").read_text(encoding="utf-8"))
    assert payload["jobs"]["broken"]["last_run_at"] is None


def test_split_cli_tokens_preserves_args_and_delivers_key_values() -> None:
    """split_cli_tokens should preserve ordinary args while extracting the key=value delivery surface."""
    args, kwargs = split_cli_tokens([
        "alpha",
        "count=2",
        "-v",
        "region=west",
        "=broken",
        "path=a=b",
    ])

    assert args == ["alpha", "-v", "=broken"]
    assert kwargs == {"count": "2", "region": "west", "path": "a=b"}


def test_invoke_cron_job_delivers_args_and_kwargs_to_callback_and_runs_hooks(tmp_path: Path) -> None:
    """invoke_cron_job should pass persisted args and kwargs directly to the callback while preserving hook flow."""
    storage = DirectoryStorage(tmp_path / "data")
    storage.config_dir().mkdir(parents=True, exist_ok=True)
    hooks = HookRegistry()
    zush_ctx = ZushCtx()
    seen: list[object] = []
    hooks.register_before_cmd(__import__("re").compile("demo.delivery"), lambda path: seen.append(("before", path)))
    hooks.register_after_cmd(__import__("re").compile("demo.delivery"), lambda path: seen.append(("after", path)))
    root = ZushGroup("zush", zush_ctx=zush_ctx, hook_registry=hooks)
    demo = click.Group("demo")

    def delivery(name: str, count: str | None = None, region: str | None = None) -> None:
        """Capture persisted cron delivery for direct assertion in this test."""
        seen.append((name, count, region))

    demo.add_command(click.Command("delivery", callback=delivery), "delivery")
    root.add_command(demo, "demo")
    write_cron_registry(
        {
            "jobs": {
                "deliver": {
                    "schedule": "* * * * *",
                    "command": "demo.delivery",
                    "args": ["alpha"],
                    "kwargs": {"count": "2", "region": "west"},
                    "detach": False,
                    "last_run_at": None,
                }
            }
        },
        storage,
    )

    invoke_cron_job(root, storage, "deliver")

    assert seen == [("before", "demo.delivery"), ("alpha", "2", "west"), ("after", "demo.delivery")]


def test_spawn_detached_cron_job_uses_detached_subprocess_contract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """spawn_detached_cron_job should launch a detached Python process bound to the active storage directory."""
    storage = DirectoryStorage(tmp_path / "data")
    captured: dict[str, object] = {}

    def fake_popen(command: list[str], **kwargs: object) -> object:
        """Capture one detached process launch request for assertion in this test."""
        captured["command"] = command
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    spawn_detached_cron_job(storage, "nightly")

    command = captured["command"]
    kwargs = captured["kwargs"]
    assert isinstance(command, list)
    assert command[0] == sys.executable
    assert command[1] == "-c"
    assert command[-2:] == [str(storage.config_dir()), "nightly"]
    assert isinstance(kwargs, dict)
    assert kwargs["cwd"] == str(storage.config_dir())
    assert isinstance(kwargs["env"], dict)
    if os.name == "nt":
        assert kwargs["creationflags"]
    else:
        assert kwargs["start_new_session"] is True