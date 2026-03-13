"""TDD: persisted config index and Plugin.persistedCtx helper."""

from __future__ import annotations

import io
import json

from click.testing import CliRunner

from zush import create_zush_group
from zush.config import Config
from zush.paths import DirectoryStorage
from zush.persistence import read_cfg_index, write_cfg_index
from zush.plugin import Plugin


def test_read_write_cfg_index_use_storage(tmp_path):
    storage = DirectoryStorage(tmp_path)
    data = {
        "plugins": {
            "zush_foo": {
                "uuid": "abc",
                "default_file": "zush.json",
            }
        }
    }
    write_cfg_index(data, storage=storage)
    assert storage.cfg_index_file().exists()
    assert read_cfg_index(storage=storage) == data


def test_plugin_persisted_ctx_creates_default_json_file(tmp_path):
    storage = DirectoryStorage(tmp_path)
    plugin = Plugin()
    plugin._bind_runtime("zush_foo", storage)

    with plugin.persistedCtx() as state:
        state["count"] = state.get("count", 0) + 1

    index = read_cfg_index(storage=storage)
    entry = index["plugins"]["zush_foo"]
    cfg_file = storage.cfg_dir() / entry["uuid"] / "zush.json"

    assert entry["default_file"] == "zush.json"
    assert cfg_file.exists()
    assert json.loads(cfg_file.read_text(encoding="utf-8")) == {"count": 1}

    with plugin.persistedCtx() as state:
        state["count"] += 1

    assert json.loads(cfg_file.read_text(encoding="utf-8")) == {"count": 2}


def test_plugin_persisted_ctx_supports_plain_text_files(tmp_path):
    storage = DirectoryStorage(tmp_path)
    plugin = Plugin()
    plugin._bind_runtime("zush_foo", storage)

    with plugin.persistedCtx("notes.txt") as handle:
        assert isinstance(handle, io.StringIO)
        handle.write("hello")

    entry = read_cfg_index(storage=storage)["plugins"]["zush_foo"]
    notes_file = storage.cfg_dir() / entry["uuid"] / "notes.txt"
    assert notes_file.read_text(encoding="utf-8") == "hello"

    with plugin.persistedCtx("notes.txt") as handle:
        assert handle.getvalue() == "hello"
        handle.seek(0)
        handle.truncate(0)
        handle.write("updated")

    assert notes_file.read_text(encoding="utf-8") == "updated"


def test_plugin_persisted_ctx_supports_toml_files(tmp_path):
    storage = DirectoryStorage(tmp_path)
    plugin = Plugin()
    plugin._bind_runtime("zush_foo", storage)

    with plugin.persistedCtx("settings.toml") as state:
        state["count"] = 1
        state["enabled"] = True

    entry = read_cfg_index(storage=storage)["plugins"]["zush_foo"]
    settings_file = storage.cfg_dir() / entry["uuid"] / "settings.toml"
    body = settings_file.read_text(encoding="utf-8")
    assert 'count = 1' in body
    assert 'enabled = true' in body

    with plugin.persistedCtx("settings.toml") as state:
        assert state["count"] == 1
        assert state["enabled"] is True


def test_plugin_persisted_ctx_supports_yaml_files(tmp_path):
    storage = DirectoryStorage(tmp_path)
    plugin = Plugin()
    plugin._bind_runtime("zush_foo", storage)

    with plugin.persistedCtx("settings.yaml") as state:
        state["count"] = 1
        state["items"] = ["a", "b"]

    entry = read_cfg_index(storage=storage)["plugins"]["zush_foo"]
    settings_file = storage.cfg_dir() / entry["uuid"] / "settings.yaml"
    body = settings_file.read_text(encoding="utf-8")
    assert 'count: 1' in body
    assert '- a' in body

    with plugin.persistedCtx("settings.yaml") as state:
        assert state["count"] == 1
        assert state["items"] == ["a", "b"]


def test_create_zush_group_binds_runtime_for_plugin_helper(tmp_path):
    env_root = tmp_path / "env"
    env_root.mkdir()
    pkg = env_root / "zush_foo"
    pkg.mkdir()
    (pkg / "__zush__.py").write_text(
        """
import click
from zush.plugin import Plugin

@click.command("save")
def save_cmd():
    with ZushPlugin.persistedCtx() as state:
        state["count"] = state.get("count", 0) + 1
    click.echo("saved")

@click.command("show")
def show_cmd():
    with ZushPlugin.persistedCtx() as state:
        click.echo(state.get("count", 0))

p = Plugin()
p.group("persist").command("save", callback=save_cmd.callback)
p.group("persist").command("show", callback=show_cmd.callback)
ZushPlugin = p
""",
        encoding="utf-8",
    )

    storage = DirectoryStorage(tmp_path / "data")
    cfg = Config(envs=[env_root], env_prefix=["zush_"])
    group = create_zush_group(config=cfg, storage=storage)
    runner = CliRunner()

    result = runner.invoke(group, ["persist", "save"])
    assert result.exit_code == 0
    assert "saved" in result.output

    result = runner.invoke(group, ["persist", "show"])
    assert result.exit_code == 0
    assert "1" in result.output


def test_plugins_with_same_name_share_cfg_entry(tmp_path):
    storage = DirectoryStorage(tmp_path)
    first = Plugin()
    second = Plugin()
    first._bind_runtime("zush_shared", storage)
    second._bind_runtime("zush_shared", storage)

    with first.persistedCtx() as state:
        state["count"] = 1

    with second.persistedCtx() as state:
        state["count"] += 1

    index = read_cfg_index(storage=storage)
    entry = index["plugins"]["zush_shared"]
    cfg_file = storage.cfg_dir() / entry["uuid"] / "zush.json"

    assert json.loads(cfg_file.read_text(encoding="utf-8")) == {"count": 2}