"""TDD: ZushGroup and merge_commands_into_group."""

import json
import os
import re
import sys
from pathlib import Path

import click
import pytest
from click.testing import CliRunner

from zush.configparse.config import load_config
from zush.core.bootstrap import create_zush_group
from zush.core.context import HookRegistry, ZushCtx
from zush.core.group import ZushGroup, add_reserved_self_group, merge_commands_into_group
from zush.core.storage import DirectoryStorage


def _invoke(group: click.Group, args: list[str]) -> click.Context:
    """Invoke group with args and return the context (after full invoke)."""
    ctx = group.make_context("zush", list(args))
    with ctx:
        group.invoke(ctx)
    return ctx


def test_merge_commands_into_group_adds_command():
    """Single command is added to group."""
    root = click.Group("root")
    commands = {"hello": click.Command("hello", callback=lambda: None)}
    merge_commands_into_group(root, [("/p", None, commands)])
    assert "hello" in root.commands
    assert root.commands["hello"].name == "hello"


def test_merge_commands_into_group_nested():
    """Dotted key creates nested groups and command."""
    root = click.Group("root")
    cmd = click.Command("run", callback=lambda: None)
    commands = {"foo.bar.run": cmd}
    merge_commands_into_group(root, [("/p", None, commands)])
    assert "foo" in root.commands
    foo = root.commands["foo"]
    assert isinstance(foo, click.Group)
    assert "bar" in foo.commands
    bar = foo.commands["bar"]
    assert isinstance(bar, click.Group)
    assert "run" in bar.commands


def test_self_is_reserved_group():
    """Plugin commands under 'self' are not merged; reserved for built-in."""
    root = click.Group("root")
    commands = {"self.foo": click.Command("foo", callback=lambda: None)}
    merge_commands_into_group(root, [("/p", None, commands)])
    assert "self" not in root.commands


def test_merge_commands_first_wins():
    """First plugin to register a path wins (overloaded index / playground)."""
    root = click.Group("root")
    cmd1 = click.Command("first", callback=lambda: None)
    cmd2 = click.Command("second", callback=lambda: None)
    merge_commands_into_group(root, [
        ("/playground", None, {"hello": cmd1}),
        ("/other", None, {"hello": cmd2}),
    ])
    assert root.commands["hello"].name == "first"


def test_zush_group_sets_ctx_obj():
    """ZushGroup sets ctx.obj to ZushCtx so commands can access it."""
    zush_ctx = ZushCtx()
    hooks = HookRegistry()
    seen_obj = []
    root = ZushGroup("zush", zush_ctx=zush_ctx, hook_registry=hooks)

    @click.pass_context
    def check(ctx):
        seen_obj.append(ctx.obj)

    root.add_command(click.Command("check", callback=check), "check")
    _invoke(root, ["check"])
    assert len(seen_obj) == 1
    # Command receives the same object the group stores (sub_ctx.obj = self.zush_ctx)
    assert seen_obj[0] is root.zush_ctx


def test_zush_group_runs_before_and_after_hooks():
    """beforeCmd and afterCmd run around command."""
    zush_ctx = ZushCtx()
    hooks = HookRegistry()
    order = []
    hooks.register_before_cmd(re.compile(".*"), lambda p: order.append(("before", p)))
    hooks.register_after_cmd(re.compile(".*"), lambda p: order.append(("after", p)))
    root = ZushGroup("zush", zush_ctx=zush_ctx, hook_registry=hooks)
    root.add_command(click.Command("x", callback=lambda: order.append("cmd")), "x")

    _invoke(root, ["x"])
    assert order == [("before", "x"), "cmd", ("after", "x")]


def test_zush_group_runs_on_error_on_exception():
    """onError runs when command raises matching exception."""
    zush_ctx = ZushCtx()
    hooks = HookRegistry()
    caught = []
    hooks.register_on_error(ValueError, lambda e: caught.append(e))
    root = ZushGroup("zush", zush_ctx=zush_ctx, hook_registry=hooks)

    def fail():
        raise ValueError("oops")

    root.add_command(click.Command("fail", callback=fail), "fail")
    with pytest.raises(ValueError):
        _invoke(root, ["fail"])
    assert len(caught) == 1
    assert caught[0].args == ("oops",)


def test_self_map_shows_live_root_commands() -> None:
    """self map should print the full root tree, not only the reserved self group."""
    root = ZushGroup("zush")
    root.add_command(click.Command("applewood", callback=lambda: None), "applewood")
    add_reserved_self_group(root)

    result = CliRunner().invoke(root, ["self", "map"])

    assert result.exit_code == 0
    assert "applewood" in result.output
    assert "self" in result.output


def test_self_config_opens_storage_config_dir(monkeypatch, tmp_path: Path) -> None:
    launched: list[str] = []
    storage = DirectoryStorage(tmp_path)
    root = ZushGroup("zush")

    if sys.platform.startswith("win") and hasattr(os, "startfile"):
        monkeypatch.setattr(os, "startfile", lambda value: launched.append(value))
    else:
        monkeypatch.setattr(click, "launch", lambda value, locate=False: launched.append(value) or 0)

    add_reserved_self_group(root, storage=storage)
    result = CliRunner().invoke(root, ["self", "config"])

    assert result.exit_code == 0
    assert launched == [str(tmp_path)]
    assert tmp_path.exists()


def test_self_config_reports_launch_failure(monkeypatch, tmp_path: Path) -> None:
    storage = DirectoryStorage(tmp_path)
    root = ZushGroup("zush")

    if sys.platform.startswith("win") and hasattr(os, "startfile"):
        def fail_startfile(value: str) -> None:
            raise OSError("boom")

        monkeypatch.setattr(os, "startfile", fail_startfile)
    else:
        monkeypatch.setattr(click, "launch", lambda value, locate=False: 127)

    add_reserved_self_group(root, storage=storage)
    result = CliRunner().invoke(root, ["self", "config"])

    assert result.exit_code != 0
    assert "Failed to open config directory" in result.output


def test_self_toggle_persists_disabled_extension_and_hides_it_on_next_boot(tmp_path: Path) -> None:
    """self toggle should persist disabled extensions and discovery should honor them next boot."""
    env_root = tmp_path / "env"
    env_root.mkdir()
    pkg = env_root / "zush_demo"
    pkg.mkdir()
    (pkg / "__zush__.py").write_text(
        """
import click

plugin = type("Plugin", (), {"commands": {"demo": click.Command("demo", callback=lambda: None)}})()
""",
        encoding="utf-8",
    )
    storage = DirectoryStorage(tmp_path / "data")
    storage.config_dir().mkdir(parents=True, exist_ok=True)
    storage.config_file().write_text(
        f'envs = ["{env_root.as_posix()}"]\nenv_prefix = ["zush_"]\ninclude_current_env = false\n',
        encoding="utf-8",
    )
    runner = CliRunner()

    initial_group = create_zush_group(storage=storage)
    initial_map = runner.invoke(initial_group, ["self", "map"])

    assert initial_map.exit_code == 0
    assert "demo" in initial_map.output

    toggled = runner.invoke(initial_group, ["self", "toggle", "zush_demo"])
    updated_config = load_config(storage=storage)

    assert toggled.exit_code == 0
    assert "disabled zush_demo" in toggled.output.lower()
    assert updated_config.disabled_extensions == ["zush_demo"]

    reloaded_group = create_zush_group(storage=storage)
    reloaded_map = runner.invoke(reloaded_group, ["self", "map"])

    assert reloaded_map.exit_code == 0
    assert "demo" not in reloaded_map.output


def test_self_toggle_reenables_disabled_extension(tmp_path: Path) -> None:
    """Toggling the same extension again should re-enable it in config."""
    storage = DirectoryStorage(tmp_path / "data")
    storage.config_dir().mkdir(parents=True, exist_ok=True)
    storage.config_file().write_text(
        'envs = []\nenv_prefix = ["zush_"]\ninclude_current_env = false\ndisabled_extensions = ["zush_demo"]\n',
        encoding="utf-8",
    )
    runner = CliRunner()
    group = create_zush_group(storage=storage)

    result = runner.invoke(group, ["self", "toggle", "zush_demo"])
    updated_config = load_config(storage=storage)

    assert result.exit_code == 0
    assert "enabled zush_demo" in result.output.lower()
    assert updated_config.disabled_extensions == []


def test_self_toggle_without_name_lists_loaded_and_disabled_extensions(tmp_path: Path) -> None:
    """self toggle without a name should inspect the current extension toggle state."""
    env_root = tmp_path / "env"
    env_root.mkdir()
    pkg = env_root / "zush_demo"
    pkg.mkdir()
    (pkg / "__zush__.py").write_text(
        """
import click

plugin = type("Plugin", (), {"commands": {"demo": click.Command("demo", callback=lambda: None)}})()
""",
        encoding="utf-8",
    )
    storage = DirectoryStorage(tmp_path / "data")
    storage.config_dir().mkdir(parents=True, exist_ok=True)
    storage.config_file().write_text(
        f'envs = ["{env_root.as_posix()}"]\nenv_prefix = ["zush_"]\ninclude_current_env = false\ndisabled_extensions = ["zush_disabled"]\n',
        encoding="utf-8",
    )
    runner = CliRunner()
    group = create_zush_group(storage=storage)

    result = runner.invoke(group, ["self", "toggle"])

    assert result.exit_code == 0
    assert "loaded this boot:" in result.output.lower()
    assert "zush_demo" in result.output
    assert "disabled next boot:" in result.output.lower()
    assert "zush_disabled" in result.output


def test_self_toggle_without_name_reports_empty_disabled_set(tmp_path: Path) -> None:
    """self toggle without a name should handle an empty disabled set cleanly."""
    storage = DirectoryStorage(tmp_path / "data")
    storage.config_dir().mkdir(parents=True, exist_ok=True)
    storage.config_file().write_text(
        'envs = []\nenv_prefix = ["zush_"]\ninclude_current_env = false\n',
        encoding="utf-8",
    )
    runner = CliRunner()
    group = create_zush_group(storage=storage)

    result = runner.invoke(group, ["self", "toggle"])

    assert result.exit_code == 0
    assert "loaded this boot:" in result.output.lower()
    assert "disabled next boot:" in result.output.lower()
    assert "(none)" in result.output.lower()


def test_add_reserved_self_group_registers_host_system_commands() -> None:
    """Host-provided system commands should be added under the reserved self group."""
    root = ZushGroup("zush")
    seen: list[str] = []

    add_reserved_self_group(
        root,
        system_commands={"doctor": click.Command("doctor", callback=lambda: seen.append("doctor"))},
    )

    result = CliRunner().invoke(root, ["self", "doctor"])

    assert result.exit_code == 0
    assert seen == ["doctor"]


def test_create_zush_group_registers_plugin_system_commands_under_self(tmp_path: Path) -> None:
    """Plugins should be able to register controlled system commands under self."""
    env_root = tmp_path / "env"
    env_root.mkdir()
    pkg = env_root / "zush_demo"
    pkg.mkdir()
    (pkg / "__zush__.py").write_text(
        """
import click
from zush.pluginloader.plugin import Plugin


def doctor() -> None:
    click.echo("plugin doctor")


plugin = Plugin()
plugin.group("demo").command("run", callback=lambda: None)
plugin.system_command("doctor", callback=doctor, help="Plugin diagnostics")
ZushPlugin = plugin
""",
        encoding="utf-8",
    )
    storage = DirectoryStorage(tmp_path / "data")
    storage.config_dir().mkdir(parents=True, exist_ok=True)
    storage.config_file().write_text(
        f'envs = ["{env_root.as_posix()}"]\nenv_prefix = ["zush_"]\ninclude_current_env = false\n',
        encoding="utf-8",
    )

    group = create_zush_group(storage=storage)
    result = CliRunner().invoke(group, ["self", "doctor"])

    assert result.exit_code == 0
    assert "plugin doctor" in result.output


def test_plugin_system_commands_do_not_override_builtin_self_commands(tmp_path: Path) -> None:
    """Plugin system commands must not replace builtin self command names."""
    env_root = tmp_path / "env"
    env_root.mkdir()
    pkg = env_root / "zush_demo"
    pkg.mkdir()
    (pkg / "__zush__.py").write_text(
        """
import click
from zush.pluginloader.plugin import Plugin


plugin = Plugin()
plugin.system_command("map", callback=lambda: click.echo("plugin map"), help="Should not override builtin map")
ZushPlugin = plugin
""",
        encoding="utf-8",
    )
    storage = DirectoryStorage(tmp_path / "data")
    storage.config_dir().mkdir(parents=True, exist_ok=True)
    storage.config_file().write_text(
        f'envs = ["{env_root.as_posix()}"]\nenv_prefix = ["zush_"]\ninclude_current_env = false\n',
        encoding="utf-8",
    )

    group = create_zush_group(storage=storage)
    result = CliRunner().invoke(group, ["self", "map"])

    assert result.exit_code == 0
    assert "plugin map" not in result.output
    assert "self" in result.output.lower()


def test_self_diagnostics_reports_no_findings_when_empty(tmp_path: Path) -> None:
    """self diagnostics should report a clean state when no diagnostics were collected."""
    storage = DirectoryStorage(tmp_path / "data")
    storage.config_dir().mkdir(parents=True, exist_ok=True)
    storage.config_file().write_text(
        'envs = []\nenv_prefix = ["zush_"]\ninclude_current_env = false\n',
        encoding="utf-8",
    )

    group = create_zush_group(storage=storage)
    result = CliRunner().invoke(group, ["self", "diagnostics"])

    assert result.exit_code == 0
    assert "(none)" in result.output.lower()


def test_self_diagnostics_reports_plugin_load_failures(tmp_path: Path) -> None:
    """self diagnostics should surface non-fatal plugin load failures collected during discovery."""
    env_root = tmp_path / "env"
    env_root.mkdir()
    bad_pkg = env_root / "zush_bad"
    bad_pkg.mkdir()
    (bad_pkg / "__zush__.py").write_text("raise RuntimeError('boom from plugin')\n", encoding="utf-8")
    storage = DirectoryStorage(tmp_path / "data")
    storage.config_dir().mkdir(parents=True, exist_ok=True)
    storage.config_file().write_text(
        f'envs = ["{env_root.as_posix()}"]\nenv_prefix = ["zush_"]\ninclude_current_env = false\n',
        encoding="utf-8",
    )

    group = create_zush_group(storage=storage)
    result = CliRunner().invoke(group, ["self", "diagnostics"])

    assert result.exit_code == 0
    assert "plugin-load-failed" in result.output
    assert "zush_bad" in result.output


def test_self_diagnostics_reports_command_conflicts(tmp_path: Path) -> None:
    """self diagnostics should surface first-wins command conflicts across plugins."""
    env_root = tmp_path / "env"
    env_root.mkdir()
    first_pkg = env_root / "zush_first"
    first_pkg.mkdir()
    (first_pkg / "__zush__.py").write_text(
        """
import click
plugin = type("Plugin", (), {"commands": {"demo.run": click.Command("run", callback=lambda: None)}})()
""",
        encoding="utf-8",
    )
    second_pkg = env_root / "zush_second"
    second_pkg.mkdir()
    (second_pkg / "__zush__.py").write_text(
        """
import click
plugin = type("Plugin", (), {"commands": {"demo.run": click.Command("run", callback=lambda: None)}})()
""",
        encoding="utf-8",
    )
    storage = DirectoryStorage(tmp_path / "data")
    storage.config_dir().mkdir(parents=True, exist_ok=True)
    storage.config_file().write_text(
        f'envs = ["{env_root.as_posix()}"]\nenv_prefix = ["zush_"]\ninclude_current_env = false\n',
        encoding="utf-8",
    )

    group = create_zush_group(storage=storage)
    result = CliRunner().invoke(group, ["self", "diagnostics"])

    assert result.exit_code == 0
    assert "command-conflict" in result.output
    assert "demo.run" in result.output
    assert "zush_second" in result.output


def test_self_cron_add_persists_job_in_base_cron_json(tmp_path: Path) -> None:
    """self cron add should persist a job in cron.json under the active base config directory."""
    env_root = tmp_path / "env"
    env_root.mkdir()
    pkg = env_root / "zush_demo"
    pkg.mkdir()
    (pkg / "__zush__.py").write_text(
        """
import click
from zush.pluginloader.plugin import Plugin


plugin = Plugin()
plugin.group("demo").command("run", callback=lambda: click.echo("ran"))
ZushPlugin = plugin
""",
        encoding="utf-8",
    )
    storage = DirectoryStorage(tmp_path / "data")
    storage.config_dir().mkdir(parents=True, exist_ok=True)
    storage.config_file().write_text(
        f'envs = ["{env_root.as_posix()}"]\nenv_prefix = ["zush_"]\ninclude_current_env = false\n',
        encoding="utf-8",
    )
    group = create_zush_group(storage=storage)

    result = CliRunner().invoke(group, ["self", "cron", "add", "*/5 * * * *", "demo.run", "alpha", "count=2"])

    assert result.exit_code == 0, (result.output, repr(result.exception))
    assert "cron-1" in result.output
    cron_path = storage.config_dir() / "cron.json"
    assert cron_path.exists()
    payload = json.loads(cron_path.read_text(encoding="utf-8"))
    assert payload == {
        "jobs": {
            "cron-1": {
                "schedule": "*/5 * * * *",
                "command": "demo.run",
                "args": ["alpha"],
                "kwargs": {"count": "2"},
                "detach": False,
                "last_run_at": None,
            }
        }
    }


def test_self_cron_add_accepts_trailing_name_and_detach_options(tmp_path: Path) -> None:
    """self cron add should keep parsing trailing args while still honoring trailing --name and -d options."""
    env_root = tmp_path / "env"
    env_root.mkdir()
    pkg = env_root / "zush_demo"
    pkg.mkdir()
    (pkg / "__zush__.py").write_text(
        """
from zush.pluginloader.plugin import Plugin


plugin = Plugin()
plugin.group("demo").command("run", callback=lambda: None)
ZushPlugin = plugin
""",
        encoding="utf-8",
    )
    storage = DirectoryStorage(tmp_path / "data")
    storage.config_dir().mkdir(parents=True, exist_ok=True)
    storage.config_file().write_text(
        f'envs = ["{env_root.as_posix()}"]\nenv_prefix = ["zush_"]\ninclude_current_env = false\n',
        encoding="utf-8",
    )
    group = create_zush_group(storage=storage)

    result = CliRunner().invoke(
        group,
        [
            "self",
            "cron",
            "add",
            "0 0 * * *",
            "demo.run",
            "alpha",
            "region=west",
            "--name",
            "nightly",
            "-d",
        ],
    )

    assert result.exit_code == 0, (result.output, repr(result.exception))
    payload = json.loads((storage.config_dir() / "cron.json").read_text(encoding="utf-8"))
    assert payload["jobs"]["nightly"] == {
        "schedule": "0 0 * * *",
        "command": "demo.run",
        "args": ["alpha"],
        "kwargs": {"region": "west"},
        "detach": True,
        "last_run_at": None,
    }


def test_self_cron_start_delegates_to_scheduler(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """self cron start should delegate to the cron scheduler for the active group and storage target."""
    storage = DirectoryStorage(tmp_path / "data")
    storage.config_dir().mkdir(parents=True, exist_ok=True)
    storage.config_file().write_text(
        'envs = []\nenv_prefix = ["zush_"]\ninclude_current_env = false\n',
        encoding="utf-8",
    )
    group = create_zush_group(storage=storage)
    seen: list[tuple[object, object]] = []

    def fake_start_scheduler(root: click.Group, active_storage: DirectoryStorage) -> None:
        """Record one delegated scheduler call for assertion in this test."""
        seen.append((root, active_storage))

    monkeypatch.setattr("zush.core.group.start_cron_scheduler", fake_start_scheduler)

    result = CliRunner().invoke(group, ["self", "cron", "start"])

    assert result.exit_code == 0, (result.output, repr(result.exception))
    assert seen == [(group, storage)]


def test_self_cron_list_prints_registered_jobs(tmp_path: Path) -> None:
    """self cron list should print persisted cron jobs from the active base cron registry."""
    storage = DirectoryStorage(tmp_path / "data")
    storage.config_dir().mkdir(parents=True, exist_ok=True)
    storage.config_file().write_text(
        'envs = []\nenv_prefix = ["zush_"]\ninclude_current_env = false\n',
        encoding="utf-8",
    )
    (storage.config_dir() / "cron.json").write_text(
        json.dumps(
            {
                "jobs": {
                    "cron-1": {
                        "schedule": "*/5 * * * *",
                        "command": "self.map",
                        "args": [],
                        "kwargs": {},
                        "detach": False,
                        "last_run_at": None,
                    },
                    "nightly": {
                        "schedule": "0 0 * * *",
                        "command": "self.diagnostics",
                        "args": [],
                        "kwargs": {},
                        "detach": True,
                        "last_run_at": "2026-04-17T00:00",
                    },
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    group = create_zush_group(storage=storage)

    result = CliRunner().invoke(group, ["self", "cron", "list"])

    assert result.exit_code == 0, (result.output, repr(result.exception))
    assert "cron-1 | */5 * * * * | self.map | attached | never" in result.output
    assert "nightly | 0 0 * * * | self.diagnostics | detached | 2026-04-17T00:00" in result.output


def test_self_cron_list_reports_empty_registry(tmp_path: Path) -> None:
    """self cron list should print a clean empty marker when no jobs are registered."""
    storage = DirectoryStorage(tmp_path / "data")
    storage.config_dir().mkdir(parents=True, exist_ok=True)
    storage.config_file().write_text(
        'envs = []\nenv_prefix = ["zush_"]\ninclude_current_env = false\n',
        encoding="utf-8",
    )
    group = create_zush_group(storage=storage)

    result = CliRunner().invoke(group, ["self", "cron", "list"])

    assert result.exit_code == 0, (result.output, repr(result.exception))
    assert "(none)" in result.output.lower()


def test_self_cron_remove_deletes_named_job(tmp_path: Path) -> None:
    """self cron remove should delete one persisted job from the active base cron registry."""
    storage = DirectoryStorage(tmp_path / "data")
    storage.config_dir().mkdir(parents=True, exist_ok=True)
    storage.config_file().write_text(
        'envs = []\nenv_prefix = ["zush_"]\ninclude_current_env = false\n',
        encoding="utf-8",
    )
    (storage.config_dir() / "cron.json").write_text(
        json.dumps(
            {
                "jobs": {
                    "cron-1": {
                        "schedule": "*/5 * * * *",
                        "command": "self.map",
                        "args": [],
                        "kwargs": {},
                        "detach": False,
                        "last_run_at": None,
                    }
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    group = create_zush_group(storage=storage)

    result = CliRunner().invoke(group, ["self", "cron", "remove", "cron-1"])

    assert result.exit_code == 0, (result.output, repr(result.exception))
    assert "removed cron-1" in result.output.lower()
    payload = json.loads((storage.config_dir() / "cron.json").read_text(encoding="utf-8"))
    assert payload == {"jobs": {}}
